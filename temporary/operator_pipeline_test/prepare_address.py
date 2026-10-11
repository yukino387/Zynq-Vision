from pathlib import Path
import re
import shutil

base = Path(__file__).resolve().parent / "build"
source = base / "combined_src"
out = base / "address_src"
out.mkdir(parents=True, exist_ok=True)
for path in source.iterdir():
    if path.suffix in (".cpp", ".h"):
        shutil.copy2(path, out / path.name)


def bind(name):
    return "\n#pragma HLS BIND_OP variable="+name+" op=mul impl=fabric latency=3\n"


path = out / "std_conv.cpp"
code = path.read_text(encoding="utf-8")
code = code.replace("ap_uint<18> size=fm_size*fm_size;", "ap_uint<18> size=fm_size*fm_size;"+bind("size"))
code = code.replace("int base_addr1=n*size+(fm_row-P)*fm_size+(fm_col-P);",
                    "int channel_offset=n*size;"+bind("channel_offset")+
                    "int row_offset=(fm_row-P)*fm_size;"+bind("row_offset")+
                    "int base_addr1=channel_offset+row_offset+fm_col-P;")
code = code.replace("int base_addr2=base_addr1+fm_row*fm_size+fm_col;",
                    "int row_extra=fm_row*fm_size;"+bind("row_extra")+
                    "int base_addr2=base_addr1+row_extra+fm_col;")
code = code.replace("#pragma HLS RESOURCE variable=rr_offset core=Mul_LUT", bind("rr_offset"))
code = code.replace("int base_addr=m*ch_in_kk + n*K*K;",
                    "int kernel_offset=m*ch_in_kk;"+bind("kernel_offset")+
                    "int base_addr=kernel_offset+n*K*K;")
code = code.replace("unsigned short nn=k/(K*K);", "int block_offset=mm*ch_in_kk;"+bind("block_offset")+
                    "unsigned short nn=k/(K*K);")
for lane in range(4):
    code = code.replace("(mm+"+str(lane)+")*ch_in_kk", "(block_offset+"+str(lane)+"*ch_in_kk)")
code = code.replace("int base_addr=(m+mm)*o_size+(fm_row+rr)*o_fm_size+fm_col;",
                    "int output_channel=(m+mm)*o_size;"+bind("output_channel")+
                    "int output_row=(fm_row+rr)*o_fm_size;"+bind("output_row")+
                    "int base_addr=output_channel+output_row+fm_col;")
path.write_bytes(code.encode("utf-8"))

path = out / "pwconv.cpp"
code = path.read_text(encoding="utf-8").replace("#define Tm 8", "#define Tm 16")
code = code.replace("ap_uint<18> size=fm_size*fm_size;", "ap_uint<18> size=fm_size*fm_size;"+bind("size"))
code = code.replace("int base_addr=n*size+basePixAddr;", "int channel_offset=n*size;"+bind("channel_offset")+
                    "int base_addr=channel_offset+basePixAddr;")
code = code.replace("wt_buff[mm][nn]=*(weight + (m+mm)*ch_in + (n+nn));",
                    "int weight_offset=(m+mm)*ch_in;"+bind("weight_offset")+
                    "wt_buff[mm][nn]=*(weight+weight_offset+n+nn);")
code = code.replace("*(fm_out+(m+mm)*size+basePixAddr+i)=tmp2;",
                    "int output_offset=(m+mm)*size;"+bind("output_offset")+
                    "*(fm_out+output_offset+basePixAddr+i)=tmp2;")
path.write_bytes(code.encode("utf-8"))

path = out / "maxpool.cpp"
code = path.read_text(encoding="utf-8")
code = re.sub(r"#pragma HLS RESOURCE variable=(\w+) core=Mul_LUT", lambda m: bind(m[1]), code)
for name in ("n_base", "r_base", "nn_size", "ii_fsize", "size"):
    # Only definitions whose root operation is multiplication receive this binding.
    code = re.sub(r"(int "+name+r"\s*=\s*[^;]+\*[^;]+;)", lambda m: m[0]+bind(name), code)
code = code.replace("data_t fm_in_buff[Tn][Tr*2][Tc*2];",
                    "data_t fm_in_buff[Tn][Tr*2][Tc*2];\n"
                    "#pragma HLS ARRAY_PARTITION variable=fm_in_buff cyclic factor=2 dim=2\n"
                    "#pragma HLS ARRAY_PARTITION variable=fm_in_buff cyclic factor=2 dim=3")
path.write_bytes(code.encode("utf-8"))
print(out)
