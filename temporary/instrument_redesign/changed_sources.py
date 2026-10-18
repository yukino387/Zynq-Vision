from pathlib import Path
import json
backup=Path('temporary/instrument_redesign/before')
changed=[]
for p in backup.rglob('*'):
 if p.is_file():
  current=Path(*p.relative_to(backup).parts)
  if current.exists() and current.read_bytes()!=p.read_bytes(): changed.append(current.as_posix())
print(json.dumps({'changed_source_files':changed,'new_source_files':['apps/web/src/instrument.css','apps/web/src/components/AssetThumbnail.vue'],'additional_build_config':'apps/mobile/vite.config.ts'},ensure_ascii=False,indent=2))
