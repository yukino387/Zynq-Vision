from pathlib import Path
p=Path('apps/web/src/views/Models.vue');s=p.read_text(encoding='utf-8').replace("new Set<string>(step.states).has(r.status ?? '')","step.states.some(state => state === r.status)");p.write_bytes(s.encode())
