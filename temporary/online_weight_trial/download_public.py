import urllib.request,hashlib,json,importlib.util
from pathlib import Path
url='https://github.com/winthegame259/steel-surface-defect-detection/releases/download/v1.0.0/neu_det_yolov8n_best.onnx'
p=Path('temporary/online_weight_trial/neu_det_yolov8n_best.onnx')
request=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
with urllib.request.urlopen(request,timeout=45) as response,p.open('wb') as out:
 while chunk:=response.read(1024*1024):out.write(chunk)
info={'url':url,'file':str(p),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
Path('temporary/online_weight_trial/download.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
print(json.dumps(info));print('onnx_available',bool(importlib.util.find_spec('onnx')))
