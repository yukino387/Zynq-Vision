from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[2]
out = Path(__file__).resolve().parent / "build/bias_loop_src"
out.mkdir(parents=True, exist_ok=True)
for path in (root / "hardware/hls/src").iterdir():
    if path.suffix in (".cpp", ".h"):
        shutil.copy2(path, out / path.name)
for name, count in (("std_conv.cpp", "ch_out"), ("pwconv.cpp", "M")):
    path = out / name
    source = path.read_text(encoding="utf-8")
    old = "memcpy((data_t*)bias_buff,(const data_t*)bias,sizeof(data_t)*"+count+");"
    new = ("for (unsigned short index=0; index<"+count+"; ++index) {\n"
           "#pragma HLS PIPELINE II=1\n"
           "        bias_buff[index/Tm][index%Tm] = bias[index];\n    }")
    assert source.count(old) == 1
    path.write_text(source.replace(old, new), encoding="utf-8")
print(out)
