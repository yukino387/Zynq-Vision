import json
from pathlib import Path
ROOT=Path(r"C:/00_workplace/fpga/cnn_accelerator")
src=json.loads((ROOT/"temporary/model_train_20261018/milk_spec.json").read_text(encoding="utf-8"))
items=src["items"]
# use 58 for training; keep one last capture per class as a tiny sanity check
for it in items: it["split"]="train"
for cls in (0,1):
    group=[i for i in items if i["boxes"][0]["classId"]==cls]
    group[-1]["split"]="val"
src["options"]["epochs"]=200
src["version"]="INT8-MILK-STRAW-20261018-D"
out=ROOT/"temporary/model_train_20261018/milk_spec_all.json"
out.write_text(json.dumps(src,ensure_ascii=False,indent=1),encoding="utf-8")
from collections import Counter
print(Counter((i["split"],i["boxes"][0]["classId"]) for i in items))
