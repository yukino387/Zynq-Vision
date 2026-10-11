from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[2]
src = root / "hardware/hls/src"
out = Path(__file__).resolve().parent / "build/tile26_src"
out.mkdir(parents=True, exist_ok=True)
for path in src.iterdir():
    if path.suffix in (".cpp", ".h"):
        shutil.copy2(path, out / path.name)

path = out / "std_conv.cpp"
code = path.read_text(encoding="utf-8")
code = code.replace("#define Tr 13", "#define Tr 26").replace("#define Tc 13", "#define Tc 26")
code = code.replace("unsigned short nn,rr,cc;", "unsigned short nn,rr,cc;\n    const unsigned short tile = fm_size / stride < 26 ? 13 : 26;")
code = code.replace("rr<Tr+K-1", "rr<tile+K-1").replace("cc<Tc+K-1", "cc<tile+K-1")
code = code.replace("rr<TRin", "rr<tile*2+1").replace("cc<TCin", "cc<tile*2+1")
code = code.replace("unsigned short m){", "unsigned short m, unsigned short tile){")
code = code.replace("unsigned short stride){\n#pragma HLS ARRAY_PARTITION", "unsigned short stride, unsigned short tile){\n#pragma HLS ARRAY_PARTITION")
code = code.replace("for(rr=0;rr<Tr;rr++)", "for(rr=0;rr<tile;rr++)")
code = code.replace("for(cc=0;cc<Tc;cc++)", "for(cc=0;cc<tile;cc++)")
code = code.replace("unsigned short o_fm_size=(stride==1)?fm_size:fm_size/2;", "unsigned short o_fm_size=(stride==1)?fm_size:fm_size/2;\nconst unsigned short tile = o_fm_size < 26 ? 13 : 26;")
code = code.replace("\t//pingpong buffer ", "\tconst unsigned short tile = fm_size / stride < 26 ? 13 : 26;\n\t//pingpong buffer ")
code = code.replace("load_bias(fm_out_buff,bias_buff,m);", "load_bias(fm_out_buff,bias_buff,m,tile);")
code = code.replace("wt_buff1,stride);", "wt_buff1,stride,tile);").replace("wt_buff2,stride);", "wt_buff2,stride,tile);")
code = code.replace("if(c+Tc>=fm_size)", "const unsigned short tile = fm_size < 26 ? 13 : 26;\n    if(c+tile>=fm_size)")
code = code.replace("r+Tr", "r+tile").replace("c+Tc", "c+tile")
# Avoid processing a nonexistent next tile for a single-tile layer.
code = code.replace("while(true){", "while(next_m < ch_out){")
path.write_text(code, encoding="utf-8")
print(out)
