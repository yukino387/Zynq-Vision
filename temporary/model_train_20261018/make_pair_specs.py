import hashlib, json
from pathlib import Path
ROOT=Path(r"C:/00_workplace/fpga/cnn_accelerator")
real=json.loads((ROOT/"temporary/model_train_20261018/milk_spec_all.json").read_text(encoding="utf-8"))
syn=json.loads((ROOT/"temporary/model_train_20261018/pair_syn/meta.json").read_text(encoding="utf-8"))
items=[]
for i,m in enumerate(syn):
    p=Path(m["path"]); items.append({"id":f"pair_{i:05d}","path":str(p),"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),
        "raw":False,"width":416,"height":416,"split":"val" if i%5==0 else "train","boxes":m["boxes"]})
pre=dict(real); pre["items"]=items; pre["options"]=dict(real["options"],epochs=100,batchSize=8,learningRate=0.001); pre["version"]="INT8-MILK-PAIR-PRE"
(ROOT/"temporary/model_train_20261018/pair_pre_spec.json").write_text(json.dumps(pre,ensure_ascii=False,indent=1),encoding="utf-8")
ft=json.loads((ROOT/"temporary/model_train_20261018/milk_spec_all.json").read_text(encoding="utf-8"))
ft["options"]=dict(ft["options"],epochs=80,learningRate=0.0005); ft["version"]="INT8-MILK-PAIR-FT"
(ROOT/"temporary/model_train_20261018/pair_ft_spec.json").write_text(json.dumps(ft,ensure_ascii=False,indent=1),encoding="utf-8")
print("pre",len(items),"ft",len(ft["items"]))
