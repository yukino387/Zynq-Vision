#include"std_conv.h"

static unsigned short spatial_tile(unsigned short size) {
    return size == 7 ? 7 : 14;
}

//config
// The size of the block ofm of a single calculation
#define Tr 14   // height
#define Tc 14   // width
#define Tn 4    // Number of channels calculated at a time
#define Tm 32   // Number of convolution kernels calculated in a single time

#define K 3    // kernel size
#define P 1    // padding
#define MAX_LEN 512  // Maximum number of input channels

// block ifm size(height and width) for each calculation, and stride=2
#define TRin (Tr-1)*2+K   //S=2 => TRin=(Tr-1)*2+K=27
#define TCin (Tr-1)*2+K
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

// load input tile In[n:n+Tn][fm_row:fm_row+Tr+K-1][fm_col:fm_col+Tc+K-1] or
// In[n:n+Tn][fm_row:fm_row+TRin][fm_col:fm_col+TCin]
template<unsigned Lane>
void load_input_plane(data_t plane[TRin][TCin], data_t* input,
                      int base, ap_uint<18> size, ap_uint<9> fm_size,
                      ap_uint<9> input_row, ap_uint<9> input_col,
                      ap_uint<1> padding, ap_uint<6> extent, bool valid) {
#pragma HLS INLINE off
    const ap_uint<6> first=input_col<padding ? 1 : 0;
    const ap_uint<10> remaining=ap_uint<10>(fm_size)+padding-input_col;
    const ap_uint<6> last=remaining<extent ? ap_uint<6>(remaining) : extent;
    for(ap_uint<6> rr=0; rr<extent; ++rr) {
        const ap_uint<10> row=ap_uint<10>(input_row)+rr;
        if(!valid || row<padding || row>=ap_uint<10>(fm_size)+padding) {
            for(ap_uint<6> cc=0; cc<extent; ++cc) {
#pragma HLS PIPELINE II=1
                plane[rr][cc]=data_t(0);
            }
        } else {
            ap_uint<15> row_offset=rr*fm_size;
#pragma HLS BIND_OP variable=row_offset op=mul impl=dsp latency=3
            const int row_base=base+int(Lane*size)+int(row_offset);
            if(first!=0)
                plane[rr][0]=data_t(0);
            for(ap_uint<6> cc=first; cc<last; ++cc) {
#pragma HLS PIPELINE II=1
                plane[rr][cc]=input[row_base+int(cc)];
            }
            for(ap_uint<6> cc=last; cc<extent; ++cc) {
#pragma HLS PIPELINE II=1
                plane[rr][cc]=data_t(0);
            }
        }
    }
}

void load_input(data_t fm_in_buff[Tn][TRin][TCin],
                data_t* in1, data_t* in2, data_t* in3, data_t* in4,
                ap_uint<10> n, unsigned short fm_row, unsigned short fm_col,
                ap_uint<9> fm_size, ap_uint<2> stride, ap_uint<2> kernel, ap_uint<10> ch_in) {
    if(n>=ch_in) return;
#pragma HLS ARRAY_PARTITION variable=fm_in_buff complete dim=1
#pragma HLS DATAFLOW
    const ap_uint<1> padding=kernel==1 ? 0 : 1;
    const unsigned short tile=spatial_tile(stride==2 ? fm_size>>1 : fm_size);
    const ap_uint<6> extent=stride==2 ? tile*2+1 : tile+int(kernel)-1;
    const ap_uint<9> input_row=stride==2 ? fm_row<<1 : fm_row;
    const ap_uint<9> input_col=stride==2 ? fm_col<<1 : fm_col;
    ap_uint<18> size=fm_size*fm_size;
#pragma HLS BIND_OP variable=size op=mul impl=dsp latency=3
    int channel_offset=n*size;
#pragma HLS BIND_OP variable=channel_offset op=mul impl=dsp latency=3
    ap_int<10> row_start=ap_int<10>(input_row)-ap_int<10>(padding);
    ap_int<20> row_offset=row_start*ap_int<10>(fm_size);
#pragma HLS BIND_OP variable=row_offset op=mul impl=dsp latency=3
    const int base=channel_offset+int(row_offset)+int(input_col)-int(padding);
    load_input_plane<0>(fm_in_buff[0],in1,base,size,fm_size,input_row,input_col,padding,extent,n+0<ch_in);
    load_input_plane<1>(fm_in_buff[1],in2,base,size,fm_size,input_row,input_col,padding,extent,n+1<ch_in);
    load_input_plane<2>(fm_in_buff[2],in3,base,size,fm_size,input_row,input_col,padding,extent,n+2<ch_in);
    load_input_plane<3>(fm_in_buff[3],in4,base,size,fm_size,input_row,input_col,padding,extent,n+3<ch_in);
}


//load weight tile W[m:m+Tm][n:n+Tn][:][:]
template<unsigned Lane>
void load_weight_lane(data_t bank[Tm/4][Tn][K][K], data_t* weights,
                      int base, int ch_in_kk, ap_uint<10> n,
                      ap_uint<10> m, ap_uint<10> ch_in,
                      ap_uint<10> ch_out, ap_uint<2> kernel) {
#pragma HLS INLINE off
#pragma HLS ARRAY_PARTITION variable=weight_cache complete dim=1
#pragma HLS ARRAY_PARTITION variable=weight_cache complete dim=2
#pragma HLS BIND_STORAGE variable=weight_cache type=ram_1p impl=bram
    const unsigned short elements = kernel == 1 ? 1 : 9;
    for(unsigned short group=0; group<Tm/4; ++group) {
#pragma HLS LOOP_FLATTEN off
        const unsigned short channel=4*group+Lane;
        int block_offset=channel*ch_in_kk;
#pragma HLS BIND_OP variable=block_offset op=mul impl=dsp latency=3
        const bool valid=m+channel<ch_out;
        data_t values[Tn*K*K];
        if (cache_enabled && cache_reuse) {
            for(unsigned short k=0; k<Tn*elements; ++k) {
#pragma HLS PIPELINE II=1
                values[k]=weight_cache[Lane][group][n*elements+k];
            }
        } else if (valid) {
            const unsigned count=(ch_in-n < Tn ? unsigned(ch_in-n) : Tn)*elements;
            // Keep DDR reads unconditional and contiguous so HLS can form a burst.
            for(unsigned short k=0; k<Tn*elements; ++k) {
#pragma HLS PIPELINE II=1
                values[k]=0;
            }
            for(unsigned short k=0; k<count; ++k) {
#pragma HLS PIPELINE II=1
                values[k]=weights[base+block_offset+k];
            }
        } else {
            for(unsigned short k=0; k<Tn*elements; ++k) {
#pragma HLS PIPELINE II=1
                values[k]=data_t(0);
            }
        }
        for(unsigned short k=0; k<Tn*elements; ++k) {
#pragma HLS PIPELINE II=1
            const unsigned short nn=kernel == 1 ? k : k/9;
            const unsigned short i=kernel == 1 ? 0 : (k%9)/3;
            const unsigned short j=kernel == 1 ? 0 : k%3;
            const data_t value=values[k];
            if (cache_enabled && !cache_reuse) weight_cache[Lane][group][n*elements+k]=value;
            bank[group][nn][i][j]=n+nn<ch_in ? value : data_t(0);
        }
    }
}

void load_weight(data_t wt_buff[4][Tm/4][Tn][K][K],
                 data_t* w1,data_t* w2,data_t* w3,data_t* w4,
                 ap_uint<10> n,ap_uint<10> m,
                 ap_uint<10> ch_in,ap_uint<10> ch_out,ap_uint<2> kernel) {
    if(n>=ch_in) return;
#pragma HLS INLINE off
#pragma HLS DATAFLOW
#pragma HLS ARRAY_PARTITION variable=wt_buff complete dim=1
#pragma HLS ARRAY_PARTITION variable=wt_buff complete dim=2
#pragma HLS ARRAY_PARTITION variable=wt_buff complete dim=3
    const int elements=kernel == 1 ? 1 : 9;
    int ch_in_kk=ch_in*elements;
#pragma HLS RESOURCE variable=ch_in_kk core=Mul_LUT
    int kernel_offset=m*ch_in_kk;
#pragma HLS BIND_OP variable=kernel_offset op=mul impl=dsp latency=3
    const int base=kernel_offset+n*elements;
    load_weight_lane<0>(wt_buff[0],w1,base,ch_in_kk,n,m,ch_in,ch_out,kernel);
    load_weight_lane<1>(wt_buff[1],w2,base,ch_in_kk,n,m,ch_in,ch_out,kernel);
    load_weight_lane<2>(wt_buff[2],w3,base,ch_in_kk,n,m,ch_in,ch_out,kernel);
    load_weight_lane<3>(wt_buff[3],w4,base,ch_in_kk,n,m,ch_in,ch_out,kernel);
}

void load_bias(int32_t fm_out_buff[4][Tm/4][Tr][Tc],
               int32_t bias_buff[(MAX_LEN+Tm-1)/Tm][Tm],
               ap_uint<10> m,ap_uint<10> ch_out,unsigned short tile){
    int rr,cc,mm;
    for(rr=0;rr<tile;rr++)
        for(cc=0;cc<tile;cc++){
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
             ap_uint<2> stride, unsigned short tile, ap_uint<10> ch_out, ap_uint<2> kernel,bool enabled){
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
                for(cc=0;cc<tile;cc++){
                #pragma HLS PIPELINE II=1
                    for(mm=0;mm<Tm;mm++){
                    int16_t product[Tn];
#pragma HLS ARRAY_PARTITION variable=product complete
                    for(nn=0;nn<Tn;nn++) {
                        const unsigned short input_r = (stride == 2 ? rr << 1 : rr) + kx;
                        const unsigned short input_c = (stride == 2 ? cc << 1 : cc) + ky;
                        product[nn] = fm_in_buff[nn][input_r][input_c]*wt_buff[mm%4][mm/4][nn][kx][ky];
                    }
                    const int32_t sum = (int32_t(product[0])+product[1])+(int32_t(product[2])+product[3]);
                    fm_out_buff[mm%4][mm/4][rr][cc] += sum;
                    }
                }
}


// store fm_out_buff to Out[m:m+Tm][fm_row:fm_row+Tr][fm_col:fm_col+Tc]
void store_output(int32_t fm_out_buff[4][Tm/4][Tr][Tc],
                  data_t* out1,data_t* out2,data_t* out3,data_t* out4,
                  unsigned short fm_row, unsigned short fm_col, ap_uint<10> m,
                  ap_uint<9> fm_size,
                  ap_uint<2> stride,ap_uint<1> act,ap_uint<10> ch_out){
unsigned short mm,rr,cc;
unsigned short o_fm_size=(stride==1)?fm_size:(fm_size >> 1);
const unsigned short tile = spatial_tile(o_fm_size);
unsigned short o_size=o_fm_size*o_fm_size;
data_t tmp1,tmp2,tmp3,tmp4;
//
    for(mm=0;mm<Tm && m+mm<ch_out;mm+=4)
        for(rr=0;rr<tile;rr++)
            for(cc=0;cc<tile;cc++)
                {
#pragma HLS PIPELINE
                    tmp1=activate(fm_out_buff[0][mm/4][rr][cc],m+mm+0,act);
                    tmp2=activate(fm_out_buff[1][mm/4][rr][cc],m+mm+1,act);
                    tmp3=activate(fm_out_buff[2][mm/4][rr][cc],m+mm+2,act);
                    tmp4=activate(fm_out_buff[3][mm/4][rr][cc],m+mm+3,act);
                    // o_fm_size%Tr==0
                    int output_channel=(m+mm)*o_size;
#pragma HLS BIND_OP variable=output_channel op=mul impl=dsp latency=3
int output_row=(fm_row+rr)*o_fm_size;
#pragma HLS BIND_OP variable=output_row op=mul impl=dsp latency=3
int base_addr=output_channel+output_row+fm_col;
                    if (m+mm+0<ch_out) *(out1+base_addr+cc)=tmp1;
                    if (m+mm+1<ch_out) *(out2+base_addr+o_size+cc)=tmp2;
                    if (m+mm+2<ch_out) *(out3+base_addr+2*o_size+cc)=tmp3;
                    if (m+mm+3<ch_out) *(out4+base_addr+3*o_size+cc)=tmp4;
                }
}


static void load_compute(data_t next_input[Tn][TRin][TCin], data_t next_weight[4][Tm/4][Tn][K][K],
                         data_t previous_input[Tn][TRin][TCin], data_t previous_weight[4][Tm/4][Tn][K][K],
                         int32_t output[4][Tm/4][Tr][Tc],
                         data_t* in1,data_t* in2,data_t* in3,data_t* in4,
                         data_t* w1,data_t* w2,data_t* w3,data_t* w4,
                         ap_uint<10> n,ap_uint<10> m,ap_uint<10> ci,ap_uint<10> co,
                         unsigned short row,unsigned short col,ap_uint<9> size,
                         ap_uint<2> stride,ap_uint<2> kernel,unsigned short tile,bool enabled) {
#pragma HLS INLINE off
#pragma HLS DATAFLOW
    load_input(next_input,in1,in2,in3,in4,n,row,col,size,stride,kernel,ci);
    load_weight(next_weight,w1,w2,w3,w4,n,m,ci,co,kernel);
    compute(previous_input,output,previous_weight,stride,tile,co-m,kernel,enabled);
}

// compute Out[m:m+Tm][fm_row:fm_row+Tr][fm_col:fm_col+Tc]
void compute_output(int32_t fm_out_buff[4][Tm/4][Tr][Tc],
                    int32_t bias_buff[(MAX_LEN+Tm-1)/Tm][Tm],
                    data_t* in1,data_t* in2,data_t* in3,data_t* in4,
                    data_t* w1,data_t* w2,data_t* w3,data_t* w4,
                    ap_uint<10> m,ap_uint<9> fm_size,ap_uint<10> ch_in,ap_uint<10> ch_out,
                    unsigned short fm_row,unsigned short fm_col,ap_uint<2> stride, ap_uint<2> kernel){
    const unsigned short tile = spatial_tile(stride == 2 ? fm_size >> 1 : fm_size);
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
                 in1,in2,in3,in4,w1,w2,w3,w4,0,m,ch_in,ch_out,fm_row,fm_col,fm_size,stride,kernel,tile,false);
    bool pingpong=true;
    for(ti=Tn;ti<ch_in;ti+=Tn){
        if(pingpong){
            load_compute(fm_in_buff2,wt_buff2,fm_in_buff1,wt_buff1,fm_out_buff,
                         in1,in2,in3,in4,w1,w2,w3,w4,ti,m,ch_in,ch_out,fm_row,fm_col,fm_size,stride,kernel,tile,true);
            pingpong=false;
        }
        else{
            load_compute(fm_in_buff1,wt_buff1,fm_in_buff2,wt_buff2,fm_out_buff,
                         in1,in2,in3,in4,w1,w2,w3,w4,ti,m,ch_in,ch_out,fm_row,fm_col,fm_size,stride,kernel,tile,true);
            pingpong=true;
        }
    }
    if(pingpong){
        load_compute(fm_in_buff2,wt_buff2,fm_in_buff1,wt_buff1,fm_out_buff,
                 in1,in2,in3,in4,w1,w2,w3,w4,ch_in,m,ch_in,ch_out,fm_row,fm_col,fm_size,stride,kernel,tile,true);
    }
    else{
        load_compute(fm_in_buff1,wt_buff1,fm_in_buff2,wt_buff2,fm_out_buff,
                 in1,in2,in3,in4,w1,w2,w3,w4,ch_in,m,ch_in,ch_out,fm_row,fm_col,fm_size,stride,kernel,tile,true);
    }
}


void next_block(unsigned short r,unsigned short c,ap_uint<10> m,
                unsigned short &next_r, unsigned short &next_c, ap_uint<10> &next_m,
                ap_uint<9> fm_size){
    const unsigned short tile = spatial_tile(fm_size);
    if(c+tile>=fm_size){
        if(r+tile>=fm_size){
            next_m=m+Tm;
            next_r=0;
            next_c=0;
        }
        else{
            next_m=m;
            next_r=r+tile;
            next_c=0;
        }
    }
    else{
        next_m=m;
        next_r=r;
        next_c=c+tile;
    }
}


void std_conv(data_t* in1,data_t* in2,data_t* in3,data_t* in4,
              data_t* w1,data_t* w2,data_t* w3,data_t* w4,
              int32_t* bias,
              data_t* out1,data_t* out2,data_t* out3,data_t* out4,
              ap_uint<10> ch_in,ap_uint<10> ch_out,
              ap_uint<9> fm_size,ap_uint<2> stride,ap_uint<1> act, ap_uint<2> kernel){
    int32_t bias_buff[(MAX_LEN+Tm-1)/Tm][Tm];
#pragma HLS ARRAY_PARTITION variable=bias_buff complete dim=2
    int32_t fm_out[4][Tm/4][Tr][Tc];
#pragma HLS ARRAY_PARTITION variable=fm_out complete dim=1
#pragma HLS ARRAY_PARTITION variable=fm_out complete dim=2
#pragma HLS BIND_STORAGE variable=fm_out type=ram_s2p impl=bram
    for (unsigned index=0;index<ch_out;++index) {
#pragma HLS PIPELINE II=1
        bias_buff[index/Tm][index%Tm]=bias[index];
        quant_m[index]=bias[ch_out+index]; quant_s[index]=bias[2*ch_out+index];
        quant_nm[index]=bias[3*ch_out+index]; quant_ns[index]=bias[4*ch_out+index];
    }
    quant_channels=ch_out;
    cache_enabled=kernel==1 || ch_in<=128;
    const unsigned out_size=stride==2 ? unsigned(fm_size)>>1 : unsigned(fm_size);
    const unsigned tile=spatial_tile(out_size);
    for(unsigned m=0;m<ch_out;m+=Tm) {
        cache_reuse=false;
        for(unsigned r=0;r<out_size;r+=tile) for(unsigned c=0;c<out_size;c+=tile) {
            compute_output(fm_out,bias_buff,in1,in2,in3,in4,w1,w2,w3,w4,
                           m,fm_size,ch_in,ch_out,r,c,stride,kernel);
            store_output(fm_out,out1,out2,out3,out4,r,c,m,fm_size,stride,act,ch_out);
            cache_reuse=true;
        }
    }
}
