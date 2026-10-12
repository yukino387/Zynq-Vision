"""Move padding checks out of each pipelined AXI read."""
from pathlib import Path
import shutil

base = Path(__file__).resolve().parent / 'build'
out = base / 'shared44_read_rows_src'
out.mkdir(parents=True, exist_ok=True)
for path in (base / 'shared44_read_lanes_src').iterdir():
    if path.suffix in ('.cpp', '.h'):
        shutil.copy2(path, out / path.name)
path = out / 'std_conv.cpp'
code = path.read_text(encoding='utf-8')
start = code.index('template<unsigned Lane>')
end = code.index('void load_input(', start)
replacement = '''template<unsigned Lane>
void load_input_plane(data_t plane[TRin][TCin], data_t* input,
                      int base, ap_uint<18> size, ap_uint<9> fm_size,
                      ap_uint<9> input_row, ap_uint<9> input_col,
                      ap_uint<1> padding, ap_uint<6> extent) {
#pragma HLS INLINE off
    const ap_uint<6> first=input_col<padding ? 1 : 0;
    const ap_uint<10> remaining=ap_uint<10>(fm_size)+padding-input_col;
    const ap_uint<6> last=remaining<extent ? ap_uint<6>(remaining) : extent;
    for(ap_uint<6> rr=0; rr<extent; ++rr) {
        const ap_uint<10> row=ap_uint<10>(input_row)+rr;
        if(row<padding || row>=ap_uint<10>(fm_size)+padding) {
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

'''
path.write_bytes((code[:start]+replacement+code[end:]).encode('utf-8'))
print(out)
