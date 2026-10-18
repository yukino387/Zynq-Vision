import hashlib, json
from pathlib import Path
ROOT=Path(r"C:/00_workplace/fpga/cnn_accelerator")
real=json.loads((ROOT/"temporary/model_train_20261018/milk_spec_all.json").read_text(encoding="utf-8"))
syn=json.loads((ROOT/"temporary/model_train_20261018/synthetic_v2/meta.json").read_text(encoding="utf-8"))
items=list(real["items"])
for i,m in enumerate(syn):
    p=Path(m["path"]); items.append({
        "id": f"syn_{i:05d}", "path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        "raw": False, "width": 416, "height": 416,
        "split": "val" if i % 5 == 0 else "train",
        "boxes": m["boxes"]})
spec=dict(real); spec["items"]=items
spec["options"]=dict(real["options"], epochs=80, batchSize=8, learningRate=0.001)
spec["version"]="INT8-MILK-STRAW-SYN-20261018"
(ROOT/"temporary/model_train_20261018/milk_syn_spec.json").write_text(json.dumps(spec,ensure_ascii=False,indent=1),encoding="utf-8")
from collections import Counter
print("items",len(items),Counter(i["split"] for i in items),"classes",spec["classes"])
