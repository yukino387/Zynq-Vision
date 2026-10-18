from pathlib import Path
p=Path('camera/create_app.py');s=p.read_text();s=s.replace('domain.set_lib(lib_name="xilffs")','domain.set_lib(lib_name="xilffs")\ndomain.set_config(option="lib", lib_name="xilffs", param="XILFFS_enable_exfat", value="true")');p.write_text(s)
