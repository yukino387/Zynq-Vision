import json,sys,subprocess,numpy as np,imageio_ffmpeg
from pathlib import Path
root=Path(__file__).resolve().parents[2];p=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'camera/desktop'));from postprocess import detect
py=detect((p/'detect_0.bin').read_bytes(),(p/'detect_1.bin').read_bytes());cs=json.loads((p/'native_detections.json').read_text());assert len(py)==len(cs)
for a,b in zip(py,cs):
 assert a['class_id']==b['ClassId'];assert abs(a['score']-b['Score'])<1e-10;assert np.allclose(a['box'],[b['X1'],b['Y1'],b['X2'],b['Y2']],atol=1e-8)
print('Decode/NMS: PASS')
for file in [p/'native_recording.mp4',*list((p/'build/ui/build/app/Recordings').glob('*.mp4'))]:
 r=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-i',str(file),'-f','null','-'],capture_output=True,text=True,encoding="utf-8",errors="replace");assert r.returncode==0,r.stderr;assert '416x416' in r.stderr and 'Video: h264' in r.stderr;print('MP4 decode PASS:',file.name)
r=json.loads((p/'board_results.json').read_text());report={'baseline_actual_ms':{'capture':39786*4/1000,'conversion':1516*4/1000,'inference':140701*4/1000,'transfer':17817*4/1000,'cycle':199869*4/1000}}
for mode in ['detect','preview']:
 frames=[t for m,f,t in r['frames'] if m==mode];report[mode]={'frames':len(frames),'fps':(len(frames)-1)/(frames[-1]-frames[0])}
assert all(s[10]==0 for s in r['stats']);(p/'build/validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
