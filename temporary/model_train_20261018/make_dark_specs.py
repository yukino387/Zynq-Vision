import json
from pathlib import Path
ROOT=Path(r"C:/00_workplace/fpga/cnn_accelerator")
base=json.loads((ROOT/"temporary/model_train_20261018/milk_spec_all.json").read_text(encoding="utf-8"))
groups=json.loads((ROOT/"temporary/model_train_20261018/scene_groups.json").read_text(encoding="utf-8"))
items=base["items"]
dark=[it for it in items if groups[it["id"]] in (2,3)]
paper=[it for it in items if groups[it["id"]] in (0,4)]
for it in items: it["split"]="train"
for cls in (0,1):
    group=[it for it in dark if it["boxes"][0]["classId"]==cls]
    for it in (group[3], group[8], group[13]): it["split"]="val"
dark_spec=dict(base); dark_spec["items"]=dark
dark_spec["options"]=dict(base["options"], epochs=150, learningRate=0.0002)
dark_spec["version"]="INT8-MILK-STRAW-DARK-20261018"
(ROOT/"temporary/model_train_20261018/milk_spec_dark.json").write_text(json.dumps(dark_spec,ensure_ascii=False,indent=1),encoding="utf-8")
for it in paper: it["split"]="val"
paper_spec=dict(base); paper_spec["items"]=paper
paper_spec["version"]="INT8-MILK-STRAW-DARK-20261018"
(ROOT/"temporary/model_train_20261018/milk_spec_paper_test.json").write_text(json.dumps(paper_spec,ensure_ascii=False,indent=1),encoding="utf-8")
from collections import Counter
print("dark", len(dark), Counter((it["split"],it["boxes"][0]["classId"]) for it in dark))
print("paper", len(paper), Counter(it["boxes"][0]["classId"] for it in paper))
