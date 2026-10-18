import json,collections
from pathlib import Path
b=Path('temporary/online_weight_trial/neu_det_yolov8n_best.onnx').read_bytes()
def varint(b,p):
 value=0;shift=0
 while True:
  n=b[p];p+=1;value|=(n&127)<<shift
  if n<128:return value,p
  shift+=7
  if shift>63:raise ValueError('Invalid protobuf integer')
def fields(b):
 p=0
 while p<len(b):
  key,p=varint(b,p);number=key>>3;wire=key&7
  if wire==0:v,p=varint(b,p)
  elif wire==2:n,p=varint(b,p);v=b[p:p+n];p+=n
  elif wire==5:v=b[p:p+4];p+=4
  elif wire==1:v=b[p:p+8];p+=8
  else:raise ValueError('Unsupported protobuf field')
  yield number,v
def sub(b,n):return next(v for k,v in fields(b) if k==n)
def value_info(b):
 name=sub(b,1).decode();t=sub(sub(b,2),1);dtype=sub(t,1);shape=sub(t,2);dims=[]
 for k,v in fields(shape):
  if k==1:
   d=list(fields(v));dims.append(d[0][1].decode() if isinstance(d[0][1],bytes) else d[0][1])
 return {'name':name,'onnxDataType':dtype,'shape':dims}
graph=sub(b,7);inputs=[];outputs=[];ops=collections.Counter();types=collections.Counter()
for k,v in fields(graph):
 if k==11:inputs.append(value_info(v))
 elif k==12:outputs.append(value_info(v))
 elif k==1:ops[sub(v,4).decode()]+=1
 elif k==5:types[sub(v,2)]+=1
result={'inputs':inputs,'outputs':outputs,'operators':dict(ops),'initializerTypes':dict(types),'currentBoardProfile':{'input':[1,1,224,224],'dtype':'INT8','outputs':[[1,33,7,7],[1,33,14,14]]},'compatible':False}
Path('temporary/online_weight_trial/public-model-inspection.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
