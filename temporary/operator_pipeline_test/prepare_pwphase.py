from pathlib import Path
import shutil

base = Path(__file__).resolve().parent / "build"
source = base / "combined_src"
out = base / "pwphase_src"
out.mkdir(parents=True, exist_ok=True)
for path in source.iterdir():
    if path.suffix in (".cpp", ".h"):
        shutil.copy2(path, out / path.name)
path = out / "pwconv.cpp"
code = path.read_text(encoding="utf-8").replace("#define Tm 8", "#define Tm 16")
start = code.index("void compute(data_t")
end = code.index("// store fm_out_buff", start)
code = code[:start] + '''void compute(data_t fm_in_buff[Tn][Tp],
             data_t fm_out_buff[Tm][Tp], data_t wt_buff[Tm][Tn]) {
#pragma HLS ARRAY_PARTITION variable=wt_buff cyclic factor=8 dim=1
#pragma HLS ARRAY_PARTITION variable=wt_buff complete dim=2
#pragma HLS ARRAY_PARTITION variable=fm_out_buff cyclic factor=8 dim=1
#pragma HLS ARRAY_PARTITION variable=fm_in_buff complete dim=1
    for (unsigned short phase=0; phase<2; ++phase)
        for (unsigned short i=0; i<Tp; ++i) {
#pragma HLS PIPELINE II=1
            for (unsigned short mm=0; mm<8; ++mm) {
#pragma HLS UNROLL
                const unsigned short channel=mm+phase*8;
                data_t p0=fm_in_buff[0][i]*wt_buff[channel][0];
                data_t p1=fm_in_buff[1][i]*wt_buff[channel][1];
                data_t p2=fm_in_buff[2][i]*wt_buff[channel][2];
                data_t p3=fm_in_buff[3][i]*wt_buff[channel][3];
                data_t a=p0+p1, b=p2+p3;
                data_t sum=a+b;
                fm_out_buff[channel][i]=data_t(fm_out_buff[channel][i]+sum);
            }
        }
}

''' + code[end:]
for name in ("wt_buff", "wt_buff1", "wt_buff2", "fm_out_buff", "fm_out1", "fm_out2"):
    code = code.replace("variable="+name+" complete dim=1", "variable="+name+" cyclic factor=8 dim=1")
path.write_bytes(code.encode("utf-8"))
print(out)
