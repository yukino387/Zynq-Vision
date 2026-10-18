from pathlib import Path
p=Path('camera/program_qspi.tcl');s=p.read_text();s=s.replace('after 500\nsource','after 500\ntargets -set -filter {name == "APU"}\nsource');s=s.replace('ps7_post_config\nconfigparams','ps7_post_config\ntargets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}\nstop\nconfigparams');p.write_bytes(s.encode())
