from pathlib import Path
import shutil

base = Path(__file__).resolve().parent / "build"
source = Path(__file__).resolve().parents[2] / "hardware" / "hls" / "src"
out = base / "rowburst_src"
out.mkdir(parents=True, exist_ok=True)
for path in source.iterdir():
    if path.suffix in (".cpp", ".h"):
        shutil.copy2(path, out / path.name)
path = out / "std_conv.cpp"
code = path.read_text(encoding="utf-8")
start = code.index("void load_input(")
end = code.index("//load weight tile", start)
loader = '''void load_input(data_t buffer[Tn][TRin][TCin],
                data_t* in1,data_t* in2,data_t* in3,data_t* in4,
                unsigned short n,unsigned short fm_row,unsigned short fm_col,
                unsigned short fm_size,unsigned short stride,unsigned short ch_in) {
    const int extent = stride == 1 ? Tr+K-1 : TRin;
    const int first_row = fm_row*stride-P;
    const int first_col = fm_col*stride-P;
    const int plane = fm_size*fm_size;
    const int first = first_col < 0 ? -first_col : 0;
    const int last = first_col+extent > fm_size ? fm_size-first_col : extent;
    for (int r=0; r<extent; ++r) {
        const int row = first_row+r;
        if (row >= 0 && row < fm_size) {
            for (int c=0; c<first; ++c) {
#pragma HLS PIPELINE II=1
                buffer[0][r][c]=0;
                buffer[1][r][c]=0;
                buffer[2][r][c]=0;
                buffer[3][r][c]=0;
            }
            for (int c=last; c<extent; ++c) {
#pragma HLS PIPELINE II=1
                buffer[0][r][c]=0;
                buffer[1][r][c]=0;
                buffer[2][r][c]=0;
                buffer[3][r][c]=0;
            }
            const int address = n*plane+row*fm_size+first_col;
            for (int c=first; c<last; ++c) {
#pragma HLS PIPELINE II=1
                buffer[0][r][c]=in1[address+c];
                buffer[1][r][c]=in2[address+plane+c];
                buffer[2][r][c]=in3[address+2*plane+c];
                buffer[3][r][c]=n+3<ch_in ? in4[address+3*plane+c] : data_t(0);
            }
        } else {
            for (int c=0; c<extent; ++c) {
#pragma HLS PIPELINE II=1
                buffer[0][r][c]=0;
                buffer[1][r][c]=0;
                buffer[2][r][c]=0;
                buffer[3][r][c]=0;
            }
        }
    }
}

'''
code = code[:start]+loader+code[end:]
code = code.replace("fm_row,fm_col,fm_size,stride);", "fm_row,fm_col,fm_size,stride,ch_in);")
path.write_text(code, encoding="utf-8")
print(out)
