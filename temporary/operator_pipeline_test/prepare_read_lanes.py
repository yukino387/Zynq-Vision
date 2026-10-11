"""Isolate four input-port handshakes without changing the convolution math."""
from pathlib import Path
import shutil

base = Path(__file__).resolve().parent / 'build'
out = base / 'shared44_read_lanes_src'
out.mkdir(parents=True, exist_ok=True)
for path in (base / 'shared44_single_src').iterdir():
    if path.suffix in ('.cpp', '.h'):
        shutil.copy2(path, out / path.name)
path = out / 'std_conv.cpp'
code = path.read_text(encoding='utf-8')
start = code.index('void load_input(')
end = code.index('//load weight tile',start)
replacement = '''template<unsigned Lane>
void load_input_plane(data_t plane[TRin][TCin], data_t* input,
                      int base, ap_uint<18> size, ap_uint<9> fm_size,
                      ap_uint<9> input_row, ap_uint<9> input_col,
                      ap_uint<1> padding, ap_uint<6> extent) {
#pragma HLS INLINE off
    for(ap_uint<6> rr=0; rr<extent; ++rr)
        for(ap_uint<6> cc=0; cc<extent; ++cc) {
#pragma HLS PIPELINE II=1
            ap_uint<15> row_offset=rr*fm_size;
#pragma HLS BIND_OP variable=row_offset op=mul impl=dsp latency=3
            if(input_row+rr>=padding && input_row+rr<fm_size+padding &&
               input_col+cc>=padding && input_col+cc<fm_size+padding)
                plane[rr][cc]=input[base+int(Lane*size)+int(row_offset)+int(cc)];
            else
                plane[rr][cc]=data_t(0);
        }
}

void load_input(data_t fm_in_buff[Tn][TRin][TCin],
                data_t* in1, data_t* in2, data_t* in3, data_t* in4,
                ap_uint<10> n, unsigned short fm_row, unsigned short fm_col,
                ap_uint<9> fm_size, ap_uint<2> stride, ap_uint<2> kernel) {
#pragma HLS ARRAY_PARTITION variable=fm_in_buff complete dim=1
#pragma HLS DATAFLOW
    const ap_uint<1> padding=kernel==1 ? 0 : 1;
    const unsigned short tile=(stride==2 ? fm_size>>1 : fm_size)<26 ? 13 : 26;
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
    load_input_plane<0>(fm_in_buff[0],in1,base,size,fm_size,input_row,input_col,padding,extent);
    load_input_plane<1>(fm_in_buff[1],in2,base,size,fm_size,input_row,input_col,padding,extent);
    load_input_plane<2>(fm_in_buff[2],in3,base,size,fm_size,input_row,input_col,padding,extent);
    load_input_plane<3>(fm_in_buff[3],in4,base,size,fm_size,input_row,input_col,padding,extent);
}


'''
code = code[:start] + replacement + code[end:]
path.write_bytes(code.encode('utf-8'))
print(out)
