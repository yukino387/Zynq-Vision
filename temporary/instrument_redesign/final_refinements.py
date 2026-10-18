from pathlib import Path
p=Path('apps/web/src/views/Models.vue');s=p.read_text(encoding='utf-8');s=s.replace("states: ['PENDING', 'QUEUED', 'CREATED']","states: ['PENDING', 'PENDING_APPROVAL', 'APPROVED', 'QUEUED', 'CREATED']")
a="devices.devices.find((d) => d.id === r.deviceId)?.name ??\n                  text(r, 'deviceId')"
# Match formatter's actual spacing without changing model/device selection behavior.
import re
s=re.sub(r"devices\.devices\.find\(\(d\) => d\.id === r\.deviceId\)\?\.name\s*\?\?\s*text\(r, 'deviceId'\)","displayName(devices.devices.find((d) => d.id === r.deviceId)?.name ?? text(r, 'deviceId'))",s)
p.write_bytes(s.encode())
p=Path('apps/mobile/src/pages/capture/index.vue');s=p.read_text(encoding='utf-8').replace('<text class="board-guide-number">01</text>','');p.write_bytes(s.encode())
