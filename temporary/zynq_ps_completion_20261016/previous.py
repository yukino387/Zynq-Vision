from pathlib import Path
p=Path('packages/contracts/src/index.ts');s=p.read_text(encoding='utf-8').replace('  cameraOnly?: boolean;','  cameraOnly?: boolean;\n  modelPayloadSha256?: string | null;');p.write_text(s,encoding='utf-8')
p=Path('apps/server/src/devices/zynq.ts');s=p.read_text().replace('modelVersion: flags & 2 ? version : null','modelVersion: flags & 2 ? version : null, modelPayloadSha256: flags & 2 ? reply.subarray(92,124).toString("hex") : null');p.write_text(s)
p=Path('apps/server/src/models/benchmarks.controller.ts');s=p.read_text();old='''    const previousModel = real && previousVersion && previousVersion !== model.version ? await this.db.model.findUnique({ where: { version: previousVersion } }) : null;''';new='''    const previousModels = real && previousVersion && previousVersion !== model.version ? await this.db.model.findMany({ where: { version: previousVersion, source: "IMPORT" } }) : [];
    let previousModel: (typeof previousModels)[number] | null = null;
    for (const candidate of previousModels) {
      const artifact = await this.models.artifact(candidate.id);
      if (artifact.weights.subarray(88,120).toString("hex") === before.reportedState.modelPayloadSha256) { previousModel = candidate; break; }
    }''';assert old in s;s=s.replace(old,new);p.write_text(s)
