from pathlib import Path
p=Path('packages/contracts/src/index.ts');s=p.read_text().replace('  inspectionEnabled?: boolean;','  inspectionEnabled?: boolean;\n  cameraOnly?: boolean;');p.write_text(s)
p=Path('apps/server/src/models/benchmarks.controller.ts');s=p.read_text();s=s.replace('import { Controller','import { randomUUID } from "node:crypto";\nimport { CommandsService } from "../devices/commands.service.js";\nimport { Controller',1);s=s.replace('@Inject(ModelsService) private models: ModelsService,','@Inject(ModelsService) private models: ModelsService,\n    @Inject(CommandsService) private commands: CommandsService,');s=s.replace('const { model, transport } =','const { model, transport, manifest, weights } =')
s=s.replace('''    const frame = await transport.captureOnce();''','''    const device = await this.db.device.findUniqueOrThrow({ where: { id: dto.deviceId } });
    const real = device.type === "ZYNQ";
    const before = transport.getStatus();
    const previousVersion = transport.getCurrentModel();
    const previousModel = real && previousVersion && previousVersion !== model.version ? await this.db.model.findUnique({ where: { version: previousVersion } }) : null;
    if (real && previousVersion !== model.version && !previousModel)
      throw new DomainError("INVALID_STATE", "Import the active model before evaluating a replacement so it can be restored");
    const frame = real ? await this.commands.run(dto.deviceId, "BENCHMARK", randomUUID(), async () => {
      try {
        await transport.deployModel(model.version, manifest, weights, async () => {});
        await transport.sendCommand("CAMERA_ONLY", 0);
        await transport.sendCommand("START_INSPECTION");
        const deadline = Date.now() + 15000;
        while (Date.now() < deadline) {
          try {
            const frame = await transport.captureOnce();
            if (frame.modelState.modelVersion === model.version && frame.outputs && frame.telemetry && frame.telemetry.errorCode === 0) return frame;
          } catch (error) { if (!(error instanceof DomainError) || error.getStatus() !== 409) throw error; }
          await new Promise((resolve) => setTimeout(resolve, 50));
        }
        throw new DomainError("DEVICE_TIMEOUT", "No complete inference frame confirmed for candidate model", 504);
      } finally {
        if (previousModel) {
          const previous = await this.models.artifact(previousModel.id);
          await transport.deployModel(previous.model.version, previous.manifest, previous.weights, async () => {});
        }
        await transport.sendCommand("CAMERA_ONLY", Number(before.reportedState.cameraOnly));
        await transport.sendCommand(before.runtimeState === "RUNNING" ? "START_INSPECTION" : "STOP_INSPECTION");
      }
    }) : await transport.captureOnce();''')
s=s.replace('source: "SIMULATION",','source: real ? "BOARD" : "SIMULATION",')
s=s.replace('label: "SIMULATED BENCHMARK",','label: real ? "BOARD INFERENCE CHECK" : "SIMULATED BENCHMARK",')
s=s.replace('candidateExecuted: false,','candidateExecuted: real,\n            frameId: frame.frameId,\n            restoredModelVersion: real ? previousVersion : null,')
s=s.replace('''"Simulator profile compatibility and current telemetry; no candidate accuracy evaluation",''','''real ? "Candidate inference on real hardware; unlabeled capture, no accuracy evaluation" : "Simulator profile compatibility and current telemetry; no candidate accuracy evaluation",''')
p.write_text(s)
