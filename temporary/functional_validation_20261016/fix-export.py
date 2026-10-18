from pathlib import Path
p=Path('apps/server/src/datasets/datasets.service.ts');s=p.read_text(encoding='utf-8');old='''name: `${asset.kind === "PREVIEW" ? "images" : "originals"}/${item.sampleId}/${asset.id}${asset.mimeType === "image/jpeg" ? ".jpg" : ".raw"}`,''';new='''name: asset.kind === "PREVIEW"
                ? `images/${item.sampleId}.jpg`
                : `originals/${item.sampleId}/${asset.id}${asset.mimeType === "image/jpeg" ? ".jpg" : ".raw"}`,''';assert old in s;s=s.replace(old,new);p.write_text(s,encoding='utf-8')
