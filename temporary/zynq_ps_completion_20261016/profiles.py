from pathlib import Path
p=Path('apps/server/src/devices/zynq.ts');s=p.read_text();s=s.replace(', firmwareVersion: "CNC2-SD-25"','');p.write_text(s)
p=Path('apps/server/src/models/models.service.ts');s=p.read_text();s=s.replace('import { simulatorManifest','import { zynqManifest } from "./zynq-profile.js";\nimport { simulatorManifest')
a=s.index('    if (device.type !== "SIMULATOR"');b=s.index('    if (differences.length)',a)
s=s[:a]+'''    if ((device.type === "SIMULATOR" && model.source !== "SIMULATION") || (device.type === "ZYNQ" && model.source !== "IMPORT"))
      throw new DomainError("MODEL_INCOMPATIBLE", "Model source is incompatible with the selected transport", 422);
    const differences = compatibility(device.type === "ZYNQ" ? zynqManifest(weights) : simulatorManifest(weights), manifest);
'''+s[b:];p.write_text(s)
p=Path('apps/server/src/deployments/deployments.controller.ts');s=p.read_text();s=s.replace('name: `SIMULATED ${model.version}`','name: model.source === "SIMULATION" ? `SIMULATED ${model.version}` : model.version');s=s.replace('source: model.source,','source: model.source === "SIMULATION" ? "SIMULATION" : "BOARD",');p.write_text(s)
