from pathlib import Path
p=Path('apps/server/src/devices/zynq.ts');s=p.read_text(encoding='utf-8');s=s.replace('''    const status = await this.request(...command);
    if (type === "SET_BRIGHTNESS"''','''    let status = await this.request(...command);
    if (type === "SET_BRIGHTNESS") {
      const deadline = Date.now() + 2000;
      while (status.telemetry?.brightness !== value && Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, 50));
        status = await this.request(0);
      }
    }
    if (type === "SET_BRIGHTNESS"''');p.write_bytes(s.encode('utf-8'))
p=Path('apps/server/src/deployments/deployments.controller.ts');s=p.read_text(encoding='utf-8');s=s.replace('''          previousVersion: transport.getCurrentModel(),''','''          previousVersion: transport.getCurrentModel(),
          receipt: { previousPayloadSha256: transport.getCurrentConfig().modelPayloadSha256 ?? null },''');a=s.index('    const previous = await this.db.model.findFirstOrThrow(');b=s.index('    const { manifest, weights, transport }',a);s=s[:a]+'''    const candidates = await this.db.model.findMany({
      where: { version: deployment.previousVersion, source: deployment.source === "BOARD" ? "IMPORT" : deployment.source },
    });
    let previous: (typeof candidates)[number] | undefined;
    for (const candidate of candidates) {
      if (deployment.source !== "BOARD") { previous = candidate; break; }
      const artifact = await this.models.artifact(candidate.id);
      if (artifact.weights.subarray(88,120).toString("hex") === (deployment.receipt as { previousPayloadSha256?: string }).previousPayloadSha256) { previous = candidate; break; }
    }
    if (!previous) throw new DomainError("INVALID_STATE", "The exact previous model artifact is unavailable for rollback");
'''+s[b:];p.write_bytes(s.encode('utf-8'))
p=Path('apps/server/src/jobs/jobs.service.ts');s=p.read_text(encoding='utf-8');Path('temporary/zynq_ps_completion_20261016/jobs.service.ts').write_bytes(p.read_bytes());s=s.replace('receipt: receipt as unknown as Prisma.InputJsonValue,','''receipt: { ...(deployment.receipt as Prisma.JsonObject), ...receipt } as unknown as Prisma.InputJsonValue,''');p.write_bytes(s.encode('utf-8'))
for name in ['camera/camera_input.cpp','camera/create_app.py','camera/int8/live_main.cpp','camera/int8/weights.S','camera/udp_output.cpp','camera/udp_output.h','hardware/camera/build.tcl']:
 p=Path(name);p.write_bytes(p.read_text(encoding='utf-8').encode('utf-8'))
