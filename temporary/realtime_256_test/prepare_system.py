from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[2]
stage = Path(__file__).resolve().parent / 'build/system'
stage.mkdir(parents=True, exist_ok=True)
shutil.copytree(root / 'temporary/realtime_256_test/build/conv/solution/impl/ip',
                stage / 'ip', dirs_exist_ok=True)
for name in ('base_system.tcl', 'camera.xdc', 'ov5640_capture.v'):
    shutil.copy2(root / 'hardware/camera' / name, stage / name)
code = (root / 'hardware/camera/build.tcl').read_text(encoding='utf-8')
code = code.replace('[file join $source_dir ../hls/build/conv/solution/impl/ip]',
                    '[file join $source_dir ip]')
(stage / 'build.tcl').write_text(code, encoding='utf-8')
