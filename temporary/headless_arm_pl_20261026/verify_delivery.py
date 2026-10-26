from pathlib import Path
import json,csv,hashlib,zipfile,sys
from PIL import Image
h=Path(__file__).resolve().parent
s=json.loads((h/'summary.json').read_text());raw=json.loads((h/'download/fixed_results.json').read_text())
with (h/'raw_timings.csv').open(encoding='utf-8-sig') as f:rows=list(csv.DictReader(f))
with (h/'raw_layer_timings.csv').open(encoding='utf-8-sig') as f:layers=list(csv.DictReader(f))
assert len(rows)==309 and len(layers)==309*33
assert sum(x['method']=='cpu' for x in rows)==9 and sum(x['method']=='pl' for x in rows)==300
assert all(float(x['total_ms'])>0 for x in rows) and s['int8_mismatches']==0
image_checks={}
for name in ('headless_arm_pl','layer_latency','repeat_distribution','statistics_table'):
    p=h/'figures'/(name+'.png')
    with Image.open(p) as im:
        assert im.width>5000
        if 'A' in im.getbands():assert im.getchannel('A').getextrema()==(255,255)
        image_checks[name]={'pixels':im.size,'dpi':im.info.get('dpi'),'opaque':True}
    export=json.loads((h/'figures'/(name+'.export.json')).read_text())
    assert (h/'figures'/(name+'.svg')).stat().st_size>0 and (h/'figures'/(name+'.pdf')).stat().st_size>0
png=json.loads((h/'png_metadata.json').read_text());pdf=json.loads((h/'pdf_metadata.json').read_text())
assert all(c['status']=='pass' for c in png['checks'])
assert abs(pdf['metadata']['width_mm']-250)<.01 and pdf['metadata']['font_resources']['all_embedded']
report={'rawMeasuredRows':len(rows),'rawLayerRows':len(layers),'armSamples':9,'plSamples':300,'noMeasuredExclusions':True,'threeInputs':len(raw['cases']),'int8Equal':True,'png':image_checks,'pdfWidthMm':pdf['metadata']['width_mm'],'pdfFontsEmbedded':True,'palette':'Graphical blue/orange contrast against white passes 3:1 screen; grayscale L* separation flagged by heuristic. Circles/diamonds, solid/dashed lines, direct labels and hatching provide redundant encodings. Normal annotations use dark text or blue. This is not an accessibility or publisher compliance certification.','rawResultSha256':hashlib.sha256((h/'download/fixed_results.json').read_bytes()).hexdigest(),'manualVisualReview':'All four figures inspected after export; no clipped labels, legend overlap or missing glyphs observed'}
(h/'delivery_checks.json').write_text(json.dumps(report,indent=2)+'\n')
with zipfile.ZipFile(h/'headless_arm_pl_package.zip','w',compression=zipfile.ZIP_DEFLATED) as z:
    for p in h.rglob('*'):
        if not p.is_file() or p.suffix=='.zip' or 'download' in p.parts and p.suffix not in ('.json','.i8','.txt'):continue
        if p.name in ('bridge.pid','git_diff_check.txt'):continue
        z.write(p,arcname=p.relative_to(h))
print('DELIVERY_CHECKS_PASS',len(rows),len(layers))
