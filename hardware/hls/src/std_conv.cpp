#include"std_conv.h"
#include "packed_multiply.h"
#include "layout.h"
#include <hls_stream.h>

static unsigned short spatial_tile(unsigned short size) {
    return size == 7 ? 7 : 14;
}

//config
// The size of the block ofm of a single calculation
#define Tr 14   // height
#define Tc 16   // width
#define Tn 8    // Number of channels calculated at a time
#define Tm 48   // Number of convolution kernels calculated in a single time

#define K 3    // kernel size
#define P 1    // padding
#define MAX_LEN 512  // Maximum number of input channels

// block ifm size(height and width) for each calculation, and stride=2
#define TRin (Tr-1)*2+K   //S=2 => TRin=(Tr-1)*2+K=27
#define TCin (Tc-1)*2+K
//======================================================
static int32_t quant_m[512], quant_s[512], quant_nm[512], quant_ns[512];
static unsigned quant_channels;

data_t requant(int32_t value, int32_t multiplier, int32_t shift) {
#pragma HLS INLINE
    const int64_t product = int64_t(value) * multiplier;
    const uint64_t magnitude = product < 0 ? uint64_t(-product) : uint64_t(product);
    const ap_uint<6> amount=shift;
    const int64_t rounded = (magnitude + (uint64_t(1) << (amount-1))) >> amount;
    const int64_t result = product < 0 ? -rounded : rounded;
    return result < -127 ? -127 : result > 127 ? 127 : data_t(result);
}

static data_t activate(int32_t value, unsigned channel, bool act) {
#pragma HLS INLINE
    if (channel >= quant_channels) return 0;
    const bool negative=act && value<0;
    const int32_t multiplier=negative ? quant_nm[channel] : quant_m[channel];
    const int32_t shift=negative ? quant_ns[channel] : quant_s[channel];
    return requant(value,multiplier,shift);
}

static data_t weight_cache[4][Tm/4][128*9];
static bool cache_enabled;
static bool cache_reuse;

template<unsigned Lane>
static void load_input_pair(data_t first_plane[TRin][TCin],data_t second_plane[TRin][TCin],
                            const uint64_t* input,unsigned n,unsigned size,unsigned row,unsigned col,
                            unsigned stride,unsigned kernel,unsigned channels) {
#pragma HLS INLINE off
    const unsigned padding=kernel==3?1:0;
    const unsigned out_size=stride==2?size>>1:size;
    const unsigned rows=out_size==7?7:14;
    const unsigned cols=out_size-col<16?out_size-col:16;
    const unsigned height=(stride==2?(rows-1)<<1:rows-1)+kernel;
    const unsigned width=(stride==2?(cols-1)<<1:cols-1)+kernel;
    const int input_row=int(stride==2?row<<1:row)-int(padding);
    const int input_col=int(stride==2?col<<1:col)-int(padding);
    const unsigned channel=n+Lane;
    const bool first_valid=channel<channels;
    const bool second_valid=channel+4<channels;
    const unsigned first_base=channel_base(channel,size);
    const unsigned second_base=channel_base(channel+4,size);
    if(size<=14) {
        uint64_t packed[2][28];
#pragma HLS ARRAY_PARTITION variable=packed complete dim=1
#pragma HLS BIND_STORAGE variable=packed type=ram_1p impl=bram
        const unsigned count=plane_size(size)>>3;
        if(first_valid) for(unsigned i=0;i<count;++i) {
#pragma HLS PIPELINE II=1
            packed[0][i]=input[(first_base>>3)+i];
        }
        if(second_valid) for(unsigned i=0;i<count;++i) {
#pragma HLS PIPELINE II=1
            packed[1][i]=input[(second_base>>3)+i];
        }
        for(unsigned y=0;y<height;++y) for(unsigned x=0;x<width;++x) {
#pragma HLS PIPELINE II=1
            const int sy=input_row+int(y),sx=input_col+int(x);
            const bool valid=sy>=0 && sy<int(size) && sx>=0 && sx<int(size);
            const unsigned index=(unsigned(sy)<<(size_level(size)+3))+unsigned(sx);
            first_plane[y][x]=first_valid && valid?data_t(packed[0][index>>3]>>((index&7)*8)):data_t(0);
            second_plane[y][x]=second_valid && valid?data_t(packed[1][index>>3]>>((index&7)*8)):data_t(0);
        }
    } else {
        const unsigned first=col==0 && padding?1:0;
        const unsigned last=input_col+int(width)>int(size)?size-input_col:width;
        const unsigned start_col=input_col+first;
        const unsigned offset=start_col&7;
        const unsigned count=(offset+last-first+7)>>3;
        for(unsigned y=0;y<height;++y) {
            const int sy=input_row+int(y);
            const bool valid=sy>=0 && sy<int(size);
            uint64_t words[2][5];
#pragma HLS ARRAY_PARTITION variable=words complete
            const unsigned position=(unsigned(sy)<<(size_level(size)+3))+start_col;
            if(valid && first_valid) for(unsigned i=0;i<count;++i) {
#pragma HLS PIPELINE II=1
                words[0][i]=input[((first_base+position)>>3)+i];
            }
            if(valid && second_valid) for(unsigned i=0;i<count;++i) {
#pragma HLS PIPELINE II=1
                words[1][i]=input[((second_base+position)>>3)+i];
            }
            for(unsigned x=0;x<width;++x) {
#pragma HLS PIPELINE II=1
                const unsigned index=offset+x-first;
                const bool inside=valid && x>=first && x<last;
                first_plane[y][x]=inside && first_valid?data_t(words[0][index>>3]>>((index&7)*8)):data_t(0);
                second_plane[y][x]=inside && second_valid?data_t(words[1][index>>3]>>((index&7)*8)):data_t(0);
            }
        }
    }
}

static void load_input(data_t input[Tn][TRin][TCin],const uint64_t* in1,const uint64_t* in2,
                       const uint64_t* in3,const uint64_t* in4,unsigned n,unsigned row,unsigned col,
                       unsigned size,unsigned stride,unsigned kernel,unsigned ci) {
#pragma HLS INLINE off
#pragma HLS DATAFLOW
    if(n<ci) {
        load_input_pair<0>(input[0],input[4],in1,n,size,row,col,stride,kernel,ci);
        load_input_pair<1>(input[1],input[5],in2,n,size,row,col,stride,kernel,ci);
        load_input_pair<2>(input[2],input[6],in3,n,size,row,col,stride,kernel,ci);
        load_input_pair<3>(input[3],input[7],in4,n,size,row,col,stride,kernel,ci);
    }
}

template<unsigned Lane>
static void load_weight_lane(data_t bank[Tm/4][Tn][K][K],const uint64_t* weights,
                             unsigned n,unsigned kernel) {
#pragma HLS INLINE off
#pragma HLS ARRAY_PARTITION variable=weight_cache complete dim=1
#pragma HLS ARRAY_PARTITION variable=weight_cache cyclic factor=2 dim=2
#pragma HLS BIND_STORAGE variable=weight_cache type=ram_s2p impl=bram
#pragma HLS DEPENDENCE variable=weight_cache inter false
    const unsigned elements=kernel==1?1:9;
    const unsigned words_per_group=kernel==1?1:9;
    uint64_t values[2][(Tm/8)*K*K];
#pragma HLS ARRAY_PARTITION variable=values complete dim=1
#pragma HLS BIND_STORAGE variable=values type=ram_1p impl=bram
    if(!cache_enabled || !cache_reuse) {
        const unsigned block=(n>>3)*4+Lane;
        const unsigned base=kernel==1?((block<<3)+(block<<2)):((block<<6)+(block<<5)+(block<<3)+(block<<2));
        unsigned group=0,word=0;
        for(unsigned i=0;i<(Tm/4)*words_per_group;++i) {
#pragma HLS PIPELINE II=1
            const uint64_t packed=weights[base+i];
            const unsigned batch=group>>1;
            const unsigned slot=(kernel==1?batch:(batch<<3)+batch)+word;
            values[group&1][slot]=packed;
            ++word;
            if(word==words_per_group) {word=0;++group;}
        }
    }
    for(unsigned batch=0;batch<Tm/8;++batch) {
        ap_uint<4> nn=0;
        ap_uint<2> ky=0,kx=0;
        for(unsigned k=0;k<Tn*elements;++k) {
#pragma HLS PIPELINE II=1
        const unsigned cache_offset=kernel==1?n+k:((n<<3)+n+k);
        const unsigned slot=(kernel==1?batch:(batch<<3)+batch)+(k>>3);
        for(unsigned parallel=0;parallel<2;++parallel) {
#pragma HLS UNROLL
            const unsigned group=(batch<<1)+parallel;
            const data_t value=cache_enabled && cache_reuse?weight_cache[Lane][group][cache_offset]
                :data_t(values[parallel][slot]>>((k&7)*8));
            if(cache_enabled && !cache_reuse)weight_cache[Lane][group][cache_offset]=value;
            bank[group][nn][ky][kx]=value;
        }
        if(kernel==1) ++nn;
        else if(kx==2) {
            kx=0;
            if(ky==2) {ky=0;++nn;} else ++ky;
        } else ++kx;
        }
    }
}

static void load_weight(data_t bank[4][Tm/4][Tn][K][K],const uint64_t* w1,const uint64_t* w2,
                        const uint64_t* w3,const uint64_t* w4,unsigned n,unsigned m,
                        unsigned ci,unsigned co,unsigned kernel) {
#pragma HLS INLINE off
#pragma HLS DATAFLOW
    if(n<ci) {
        load_weight_lane<0>(bank[0],w1,n,kernel);
        load_weight_lane<1>(bank[1],w2,n,kernel);
        load_weight_lane<2>(bank[2],w3,n,kernel);
        load_weight_lane<3>(bank[3],w4,n,kernel);
    }
}

void load_bias(int32_t fm_out_buff[4][Tm/4][Tr][Tc],
               int32_t bias_buff[(MAX_LEN+Tm-1)/Tm][Tm],
               ap_uint<10> m,ap_uint<10> ch_out,unsigned short tile){
    int rr,cc,mm;
    for(rr=0;rr<tile;rr++)
        for(cc=0;cc<Tc;cc++){
            #pragma HLS PIPELINE II=1
            for(mm=0;mm<Tm;mm++){
                #pragma HLS UNROLL
                fm_out_buff[mm%4][mm/4][rr][cc]=(m+mm<ch_out) ? bias_buff[m/Tm][mm] : data_t(0);
            }
        }
}


void compute(data_t fm_in_buff[Tn][TRin][TCin],
             int32_t fm_out_buff[4][Tm/4][Tr][Tc],
             data_t wt_buff[4][Tm/4][Tn][K][K],
             ap_uint<2> stride, unsigned short tile,unsigned short cols, ap_uint<10> ch_out, ap_uint<2> kernel,bool enabled){
    if(!enabled) return;
#pragma HLS ARRAY_PARTITION variable=wt_buff complete dim=1
#pragma HLS ARRAY_PARTITION variable=wt_buff complete dim=2
#pragma HLS ARRAY_PARTITION variable=wt_buff complete dim=3
#pragma HLS ARRAY_PARTITION variable=fm_out_buff complete dim=1
#pragma HLS ARRAY_PARTITION variable=fm_out_buff complete dim=2
#pragma HLS ARRAY_PARTITION variable=fm_in_buff complete dim=1
    unsigned short kx,ky,rr,cc,nn,mm,phase;
    for(kx=0;kx<kernel;kx++)
        for(ky=0;ky<kernel;ky++)
            for(phase=0;phase<1;phase++)
            for(rr=0;rr<tile;rr++)
                for(cc=0;cc<cols;cc++){
                #pragma HLS PIPELINE II=1
                    for(mm=0;mm<Tm;mm+=2) {
                    int16_t first[Tn],second[Tn];
#pragma HLS ARRAY_PARTITION variable=first complete
#pragma HLS ARRAY_PARTITION variable=second complete
                    for(nn=0;nn<Tn;++nn) {
                        const unsigned short input_r=(stride==2 ? rr<<1 : rr)+kx;
                        const unsigned short input_c=(stride==2 ? cc<<1 : cc)+ky;
                        multiply_pair(fm_in_buff[nn][input_r][input_c],
                                      wt_buff[mm%4][mm/4][nn][kx][ky],
                                      wt_buff[(mm+1)%4][(mm+1)/4][nn][kx][ky],first[nn],second[nn]);
                    }
                    const int32_t sum0=((int32_t(first[0])+first[1])+(int32_t(first[2])+first[3]))+((int32_t(first[4])+first[5])+(int32_t(first[6])+first[7]));
                    const int32_t sum1=((int32_t(second[0])+second[1])+(int32_t(second[2])+second[3]))+((int32_t(second[4])+second[5])+(int32_t(second[6])+second[7]));
                    fm_out_buff[mm%4][mm/4][rr][cc]+=sum0;
                    fm_out_buff[(mm+1)%4][(mm+1)/4][rr][cc]+=sum1;
                    }
                }
}


static void quantize_output(int32_t buffer[4][Tm/4][Tr][Tc],
                            hls::stream<uint64_t> words[4],
                            unsigned m,unsigned rows,unsigned cols,unsigned bytes,
                            unsigned act,unsigned co) {
#pragma HLS INLINE off
#pragma HLS ARRAY_PARTITION variable=words complete
    uint64_t partial[4]={0,0,0,0};
#pragma HLS ARRAY_PARTITION variable=partial complete
    const unsigned level=bytes==8?3:bytes==16?4:5;
    const unsigned count=rows<<level;
    for(unsigned mm=0;mm<Tm && m+mm<co;mm+=4) {
        int32_t multiplier[4],shift[4],negative_multiplier[4],negative_shift[4];
#pragma HLS ARRAY_PARTITION variable=multiplier complete
#pragma HLS ARRAY_PARTITION variable=shift complete
#pragma HLS ARRAY_PARTITION variable=negative_multiplier complete
#pragma HLS ARRAY_PARTITION variable=negative_shift complete
        for(unsigned lane=0;lane<4;++lane) {
#pragma HLS UNROLL
            const unsigned channel=m+mm+lane;
            multiplier[lane]=channel<co?quant_m[channel]:0;
            shift[lane]=channel<co?quant_s[channel]:1;
            negative_multiplier[lane]=channel<co?quant_nm[channel]:0;
            negative_shift[lane]=channel<co?quant_ns[channel]:1;
        }
        for(unsigned p=0;p<count;++p) {
#pragma HLS PIPELINE II=1
            const unsigned rr=p>>level,cc=p&(bytes-1);
            for(unsigned lane=0;lane<4;++lane) {
#pragma HLS UNROLL
                const int32_t sum=cc<cols && m+mm+lane<co?buffer[lane][mm/4][rr][cc]:0;
                const bool negative=act && sum<0;
                const data_t value=cc<cols && m+mm+lane<co?requant(sum,
                    negative?negative_multiplier[lane]:multiplier[lane],
                    negative?negative_shift[lane]:shift[lane]):data_t(0);
                if((cc&7)==0)partial[lane]=0;
                partial[lane]|=uint64_t(uint8_t(value))<<((cc&7)*8);
                if((cc&7)==7 && m+mm+lane<co)words[lane].write(partial[lane]);
            }
        }
    }
}

template<unsigned Lane>
static void write_output_stream(uint64_t* output,hls::stream<uint64_t>& words,
                                unsigned row,unsigned col,unsigned m,unsigned size,
                                unsigned rows,unsigned bytes,unsigned co) {
#pragma HLS INLINE off
    const unsigned level=bytes==8?0:bytes==16?1:2;
    const unsigned row_words=1u<<level,count=rows<<level;
    for(unsigned mm=Lane;mm<Tm && m+mm<co;mm+=4) {
        const unsigned base=channel_base(m+mm,size)+(row<<(size_level(size)+3))+col;
        if(size<=14) {
            for(unsigned i=0;i<count;++i) {
#pragma HLS PIPELINE II=1
                output[(base>>3)+i]=words.read();
            }
        } else {
            for(unsigned rr=0;rr<rows;++rr) {
                const unsigned destination=(base>>3)+(rr<<size_level(size));
                for(unsigned i=0;i<row_words;++i) {
#pragma HLS PIPELINE II=1
                    output[destination+i]=words.read();
                }
            }
        }
    }
}

static void store_output(int32_t buffer[4][Tm/4][Tr][Tc],
                         uint64_t* out1,uint64_t* out2,uint64_t* out3,uint64_t* out4,
                         unsigned row,unsigned col,unsigned m,unsigned size,unsigned stride,
                         unsigned act,unsigned co) {
#pragma HLS INLINE off
#pragma HLS DATAFLOW
    size=stride==2?size>>1:size;
    const unsigned rows=size==7?7:14;
    const unsigned cols=size-col<16?size-col:16;
    const unsigned bytes=col+cols==size?row_pitch(size)-col:16;
    hls::stream<uint64_t> words[4];
#pragma HLS ARRAY_PARTITION variable=words complete
#pragma HLS STREAM variable=words depth=32
#pragma HLS BIND_STORAGE variable=words type=fifo impl=srl
    quantize_output(buffer,words,m,rows,cols,bytes,act,co);
    write_output_stream<0>(out1,words[0],row,col,m,size,rows,bytes,co);
    write_output_stream<1>(out2,words[1],row,col,m,size,rows,bytes,co);
    write_output_stream<2>(out3,words[2],row,col,m,size,rows,bytes,co);
    write_output_stream<3>(out4,words[3],row,col,m,size,rows,bytes,co);
}

static void load_compute(data_t next_input[Tn][TRin][TCin], data_t next_weight[4][Tm/4][Tn][K][K],
                         data_t previous_input[Tn][TRin][TCin], data_t previous_weight[4][Tm/4][Tn][K][K],
                         int32_t output[4][Tm/4][Tr][Tc],
                         const uint64_t* in1,const uint64_t* in2,const uint64_t* in3,const uint64_t* in4,
                         const uint64_t* w1,const uint64_t* w2,const uint64_t* w3,const uint64_t* w4,
                         ap_uint<10> n,ap_uint<10> m,ap_uint<10> ci,ap_uint<10> co,
                         unsigned short row,unsigned short col,ap_uint<9> size,
                         ap_uint<2> stride,ap_uint<2> kernel,unsigned short tile,unsigned short cols,bool enabled) {
#pragma HLS INLINE off
#pragma HLS DATAFLOW
    load_input(next_input,in1,in2,in3,in4,n,row,col,size,stride,kernel,ci);
    load_weight(next_weight,w1,w2,w3,w4,n,m,ci,co,kernel);
    compute(previous_input,output,previous_weight,stride,tile,cols,co-m,kernel,enabled);
}

// compute Out[m:m+Tm][fm_row:fm_row+Tr][fm_col:fm_col+Tc]
void compute_output(int32_t fm_out_buff[4][Tm/4][Tr][Tc],
                    int32_t bias_buff[(MAX_LEN+Tm-1)/Tm][Tm],
                    const uint64_t* in1,const uint64_t* in2,const uint64_t* in3,const uint64_t* in4,
                    const uint64_t* w1,const uint64_t* w2,const uint64_t* w3,const uint64_t* w4,
                    ap_uint<10> m,ap_uint<9> fm_size,ap_uint<10> ch_in,ap_uint<10> ch_out,
                    unsigned short fm_row,unsigned short fm_col,ap_uint<2> stride, ap_uint<2> kernel){
    const unsigned short tile = spatial_tile(stride == 2 ? fm_size >> 1 : fm_size);
    const unsigned out_size=(stride==2?unsigned(fm_size)>>1:unsigned(fm_size));
    const unsigned cols=out_size-fm_col<16?out_size-fm_col:16;
    //pingpong buffer
    data_t fm_in_buff1[Tn][TRin][TCin];
#pragma HLS ARRAY_PARTITION variable=fm_in_buff1 complete dim=1
    data_t fm_in_buff2[Tn][TRin][TCin];
#pragma HLS ARRAY_PARTITION variable=fm_in_buff2 complete dim=1
    data_t wt_buff1[4][Tm/4][Tn][K][K];
#pragma HLS ARRAY_PARTITION variable=wt_buff1 complete dim=1
#pragma HLS ARRAY_PARTITION variable=wt_buff1 complete dim=2
#pragma HLS ARRAY_PARTITION variable=wt_buff1 complete dim=3
#pragma HLS BIND_STORAGE variable=wt_buff1 type=ram_1p impl=lutram
    data_t wt_buff2[4][Tm/4][Tn][K][K];
#pragma HLS ARRAY_PARTITION variable=wt_buff2 complete dim=1
#pragma HLS ARRAY_PARTITION variable=wt_buff2 complete dim=2
#pragma HLS ARRAY_PARTITION variable=wt_buff2 complete dim=3
#pragma HLS BIND_STORAGE variable=wt_buff2 type=ram_1p impl=lutram
    ap_uint<10> ti=0;
    //
    load_bias(fm_out_buff,bias_buff,m,ch_out,tile);
    load_compute(fm_in_buff1,wt_buff1,fm_in_buff2,wt_buff2,fm_out_buff,
                 in1,in2,in3,in4,w1,w2,w3,w4,0,m,ch_in,ch_out,fm_row,fm_col,fm_size,stride,kernel,tile,cols,false);
    bool pingpong=true;
    for(ti=Tn;ti<ch_in;ti+=Tn){
        if(pingpong){
            load_compute(fm_in_buff2,wt_buff2,fm_in_buff1,wt_buff1,fm_out_buff,
                         in1,in2,in3,in4,w1,w2,w3,w4,ti,m,ch_in,ch_out,fm_row,fm_col,fm_size,stride,kernel,tile,cols,true);
            pingpong=false;
        }
        else{
            load_compute(fm_in_buff1,wt_buff1,fm_in_buff2,wt_buff2,fm_out_buff,
                         in1,in2,in3,in4,w1,w2,w3,w4,ti,m,ch_in,ch_out,fm_row,fm_col,fm_size,stride,kernel,tile,cols,true);
            pingpong=true;
        }
    }
    if(pingpong){
        load_compute(fm_in_buff2,wt_buff2,fm_in_buff1,wt_buff1,fm_out_buff,
                 in1,in2,in3,in4,w1,w2,w3,w4,ch_in,m,ch_in,ch_out,fm_row,fm_col,fm_size,stride,kernel,tile,cols,true);
    }
    else{
        load_compute(fm_in_buff1,wt_buff1,fm_in_buff2,wt_buff2,fm_out_buff,
                 in1,in2,in3,in4,w1,w2,w3,w4,ch_in,m,ch_in,ch_out,fm_row,fm_col,fm_size,stride,kernel,tile,cols,true);
    }
}


void std_conv(const uint64_t* in1,const uint64_t* in2,const uint64_t* in3,const uint64_t* in4,
              const uint64_t* w1,const uint64_t* w2,const uint64_t* w3,const uint64_t* w4,
              int32_t* bias,
              uint64_t* out1,uint64_t* out2,uint64_t* out3,uint64_t* out4,
              ap_uint<10> ch_in,ap_uint<10> ch_out,
              ap_uint<9> fm_size,ap_uint<2> stride,ap_uint<1> act, ap_uint<2> kernel){
    int32_t bias_buff[(MAX_LEN+Tm-1)/Tm][Tm];
#pragma HLS ARRAY_PARTITION variable=bias_buff complete dim=2
    int32_t fm_out[4][Tm/4][Tr][Tc];
#pragma HLS ARRAY_PARTITION variable=fm_out complete dim=1
#pragma HLS ARRAY_PARTITION variable=fm_out complete dim=2
#pragma HLS BIND_STORAGE variable=fm_out type=ram_s2p impl=bram
    for(unsigned index=0;index<ch_out;++index) {
#pragma HLS PIPELINE II=1
        bias_buff[index/Tm][index%Tm]=bias[index];
    }
    for(unsigned index=0;index<ch_out;++index) {
#pragma HLS PIPELINE II=1
        quant_m[index]=bias[ch_out+index];
    }
    for(unsigned index=0;index<ch_out;++index) {
#pragma HLS PIPELINE II=1
        quant_s[index]=bias[2*ch_out+index];
    }
    for(unsigned index=0;index<ch_out;++index) {
#pragma HLS PIPELINE II=1
        quant_nm[index]=bias[3*ch_out+index];
    }
    for(unsigned index=0;index<ch_out;++index) {
#pragma HLS PIPELINE II=1
        quant_ns[index]=bias[4*ch_out+index];
    }
    quant_channels=ch_out;
    const unsigned out_size=stride==2 ? unsigned(fm_size)>>1 : unsigned(fm_size);
    cache_enabled=out_size>14 && (kernel==1 || ch_in<=128);
    const unsigned tile=spatial_tile(out_size);
    unsigned weight_base=0;
    for(unsigned m=0;m<ch_out;m+=Tm) {
        cache_reuse=false;
        for(unsigned r=0;r<out_size;r+=tile) for(unsigned c=0;c<out_size;c+=Tc) {
            compute_output(fm_out,bias_buff,in1,in2,in3,in4,w1+weight_base,w2+weight_base,w3+weight_base,w4+weight_base,
                           m,fm_size,ch_in,ch_out,r,c,stride,kernel);
            store_output(fm_out,out1,out2,out3,out4,r,c,m,fm_size,stride,act,ch_out);
            cache_reuse=true;
        }
        const unsigned blocks=(unsigned(ch_in)+7)>>3;
        weight_base+=kernel==1?(blocks<<5)+(blocks<<4):(blocks<<8)+(blocks<<7)+(blocks<<5)+(blocks<<4);
    }
}
