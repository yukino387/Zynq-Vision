from pathlib import Path
import re
import shutil

root = Path(__file__).resolve().parents[2]
out = Path(__file__).resolve().parent / "build/phase64_src"
out.mkdir(parents=True, exist_ok=True)
for path in (root / "hardware/hls/src").iterdir():
    if path.suffix in (".cpp", ".h"):
        shutil.copy2(path, out / path.name)
path = out / "std_conv.cpp"
code = path.read_text(encoding="utf-8")
code = code.replace("#define Tm 32", "#define Tm 64")
code = code.replace("variable=wt_buff complete dim=2", "variable=wt_buff cyclic factor=2 dim=2")
code = code.replace("variable=wt_buff1 complete dim=2", "variable=wt_buff1 cyclic factor=2 dim=2")
code = code.replace("variable=wt_buff2 complete dim=2", "variable=wt_buff2 cyclic factor=2 dim=2")
code = code.replace("unsigned short ch_in){", "unsigned short ch_in,unsigned short ch_out){")
code = code.replace("ti,m,ch_in);", "ti,m,ch_in,ch_out);")
for lane in range(4):
    code, count = re.subn(r"tmp" + str(lane+1) + r"=\*\((w[1-4][^;]+)\);",
                          r"tmp" + str(lane+1) + "=(m+mm+" + str(lane) + r"<ch_out) ? *(\1) : data_t(0);", code)
    assert count == 1
code = code.replace("unsigned short m){", "unsigned short m,unsigned short ch_out){")
code = code.replace("fm_out_buff[mm][rr][cc]=bias_buff[m/Tm][mm];", "fm_out_buff[mm][rr][cc]=(m+mm<ch_out) ? bias_buff[m/Tm][mm] : data_t(0);")
code = code.replace("load_bias(fm_out_buff,bias_buff,m);", "load_bias(fm_out_buff,bias_buff,m,ch_out);")
# Keep the original n0,n1,n2,n3 saturation order for every pixel and tap.
# Two channel phases reuse 128 multipliers across 64 output channels.
code = code.replace("unsigned short kx,ky,rr,cc,nn,mm;", "unsigned short kx,ky,rr,cc,nn,mm,phase;")
code = code.replace("for(ky=0;ky<K;ky++)", "for(ky=0;ky<K;ky++)\n            for(phase=0;phase<2;phase++)")
code = code.replace("for(nn=0;nn<Tn;nn++)", "for(nn=0;nn<2;nn++)")
code = code.replace("fm_in_buff[nn][input_r][input_c]*wt_buff[mm][nn][kx][ky]", "fm_in_buff[nn+phase*2][input_r][input_c]*wt_buff[mm][nn+phase*2][kx][ky]")
code = code.replace("unsigned short stride,unsigned short act){", "unsigned short stride,unsigned short act,unsigned short ch_out){", 1)
start = code.index("void store_output(")
end = code.index("void compute_output(", start)
store = code[start:end].replace("for(mm=0;mm<Tm;mm+=4)", "for(mm=0;mm<Tm && m+mm<ch_out;mm+=4)")
code = code[:start]+store+code[end:]
code = code.replace("fm_size,stride,act);", "fm_size,stride,act,ch_out);")
code = code.replace("while(true){", "while(next_m < ch_out){")
path.write_text(code, encoding="utf-8")
print(out)
