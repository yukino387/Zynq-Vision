import json
from pathlib import Path
ROOT=Path(r"C:/00_workplace/fpga/cnn_accelerator")
src=json.loads((ROOT/"temporary/model_train_20261018/milk_spec_all.json").read_text(encoding="utf-8"))
for it in src["items"]:
    it["boxes"][0]["classId"]=0
src["classes"]=["牛奶盒","_unused_1","_unused_2","_unused_3","_unused_4","_unused_5"]
src["version"]="INT8-MILK-BOX-DIAG-20261018"
src["options"]["epochs"]=200
out=ROOT/"temporary/model_train_20261018/milk_spec_oneclass.json"
out.write_text(json.dumps(src,ensure_ascii=False,indent=1),encoding="utf-8")
print("oneclass spec written", len(src["items"]))
