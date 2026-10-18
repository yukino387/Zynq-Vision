from pathlib import Path
p=Path('apps/web/src/components/AnnotationEditor.vue');s=p.read_text(encoding='utf-8').replace(':style="{ width: `${zoom * 100}%` }"',':style="{ width: `${zoom * 100}%`, maxWidth: `calc((var(--annotation-available) - 50px) * ${zoom * width / height})` }"');p.write_bytes(s.encode())
