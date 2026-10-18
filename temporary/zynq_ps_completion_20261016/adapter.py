from pathlib import Path
import shutil
out=Path('temporary/zynq_ps_completion_20261016')
for f in ['apps/server/src/devices/zynq.ts','apps/server/src/models/models.service.ts','apps/server/src/models/benchmarks.controller.ts','apps/server/src/deployments/deployments.controller.ts']:
 shutil.copy2(f,out/(Path(f).parent.name+'_'+Path(f).name))
p=Path('apps/server/src/devices/zynq.ts');s=p.read_text();s=s.replace('import dgram from "node:dgram";','import dgram from "node:dgram";\nimport { createHash } from "node:crypto";')
s=s.replace('  private sequence = 0;','''  private sequence = 0;
  private updating = false;
  private modelPending = new Map<number, { resolve: (reply: Buffer) => void; reject: (error: Error) => void; timer: ReturnType<typeof setTimeout> }>();''')
s=s.replace('''    this.owned = true;
    if (!this.timer)''','''    this.owned = true;
    await this.modelRpc(0).then((reply) => this.updateModelState(reply)).catch(() => undefined);
    if (!this.timer)''')
s=s.replace('''      const status = readStatus(packet);''','''      if (packet.length === 124 && packet.readUInt32LE(0) === 0x3152444d) {
        const id = packet.readUInt32LE(4), pending = this.modelPending.get(id);
        if (pending) { clearTimeout(pending.timer); this.modelPending.delete(id); pending.resolve(packet); }
        return;
      }
      const status = readStatus(packet);''')
s=s.replace('''          reportedState: {
            inspectionEnabled''','''          reportedState: {
            ...this.state.reportedState,
            inspectionEnabled''')
s=s.replace('''      if (!frame || this.decoding) return;''','''      if (!frame || this.decoding || this.updating) return;''')
s=s.replace('''            modelState: {},''','''            modelState: this.getCurrentConfig(),''')
s=s.replace('''    this.pending.clear();''','''    this.pending.clear();
    for (const pending of this.modelPending.values()) { clearTimeout(pending.timer); pending.reject(new Error("Disconnected")); }
    this.modelPending.clear();''')
start=s.index('  async deployModel(');end=s.index('  getCurrentConfig()',start)
s=s[:start]+'''  private async modelRpc(operation: number, offset = 0, data = Buffer.alloc(0)): Promise<Buffer> {
    if (!this.socket) throw new DomainError("DEVICE_OFFLINE", "Connect device first", 409);
    const attempts = operation === 2 || operation === 3 ? 3 : 1;
    for (let attempt = 0; attempt < attempts; attempt++) {
      const id = ++this.sequence, packet = Buffer.alloc(20 + data.length);
      packet.writeUInt32LE(0x314c444d); packet.writeUInt32LE(id, 4); packet.writeUInt32LE(operation, 8); packet.writeUInt32LE(offset, 12); packet.writeUInt32LE(data.length, 16); data.copy(packet, 20);
      try {
        const reply = await new Promise<Buffer>((resolve, reject) => {
          const timer = setTimeout(() => { this.modelPending.delete(id); reject(new DomainError("DEVICE_TIMEOUT", "Model protocol response timed out", 504)); }, operation === 0 ? 1200 : 5000);
          this.modelPending.set(id, { resolve, reject, timer });
          this.socket!.send(packet, this.port, this.host, (error) => { if (error) { clearTimeout(timer); this.modelPending.delete(id); reject(error); } });
        });
        const result = reply.readUInt32LE(8);
        if (result) throw new DomainError(result === 4 ? "CHECKSUM_ERROR" : "COMMAND_REJECTED", `Board model operation ${operation} rejected: ${result}`, 409);
        return reply;
      } catch (error) { if (!(error instanceof DomainError) || error.getStatus() !== 504 || attempt === attempts - 1) throw error; }
    }
    throw new Error("Model request failed");
  }
  private updateModelState(reply: Buffer) {
    const flags = reply.readUInt32LE(24);
    this.capabilities.modelUpdate = Boolean(flags & 1);
    this.capabilities.localStorage = Boolean(flags & 1);
    this.capabilities.offlineInference = Boolean(flags & 2);
    this.capabilities.modelVersion = true;
    const version = reply.subarray(28, 92).toString("ascii").split("\\0")[0];
    this.state.reportedState = { ...this.state.reportedState, modelVersion: flags & 2 ? version : null, firmwareVersion: "CNC2-SD-25" };
    return { flags, version, digest: reply.subarray(92, 124).toString("hex") };
  }
  async deployModel(version: string, manifest: ModelManifest, weights: Buffer, progress: (stage: string) => Promise<void>): Promise<DeploymentReceipt> {
    if (!this.owned || !this.capabilities.modelUpdate) throw new DomainError("NO_CAPABILITY", "Connect CNC2 firmware with an available SD card", 422);
    if (weights.length !== 6416360 || weights.readUInt32LE(0) !== 0x314e4e43 || weights.readUInt32LE(4) !== 1 || weights.readUInt32LE(8) !== 6350208 || weights.readUInt32LE(12) !== 66024 || weights.readUInt32LE(16) || weights.readUInt32LE(20) || weights.subarray(24,88).toString("ascii").split("\\0")[0] !== version || createHash("sha256").update(weights).digest("hex") !== manifest.weights.sha256 || createHash("sha256").update(weights.subarray(128)).digest("hex") !== weights.subarray(88,120).toString("hex")) throw new DomainError("MODEL_INCOMPATIBLE", "Invalid fixed-graph SD model package or version", 422);
    const digest = weights.subarray(88,120).toString("hex"), wasRunning = this.running;
    this.updating = true;
    try {
      await this.sendCommand("STOP_INSPECTION");
      await progress("DOWNLOADING"); await this.modelRpc(1);
      for (let offset = 0; offset < weights.length; offset += 1400) {
        const data = weights.subarray(offset, offset + 1400), reply = await this.modelRpc(2, offset, data);
        if (reply.readUInt32LE(12) < offset + data.length) throw new DomainError("COMMAND_REJECTED", "Board did not acknowledge model bytes", 409);
      }
      await progress("VERIFYING"); await this.modelRpc(3); await progress("VERIFIED");
      await progress("ACTIVATING"); await this.modelRpc(4); await progress("SELF_TEST");
      const deadline = Date.now() + 15000;
      while (Date.now() < deadline) {
        const info = this.updateModelState(await this.modelRpc(0));
        if (info.version === version && info.digest === digest && (info.flags & 10) === 10 && !(info.flags & 16)) {
          this.latest = null; this.assembler.clear();
          return { modelVersion: version, sha256: manifest.weights.sha256, downloaded: true, verified: true, loaded: true, selfTest: true, active: true, simulated: false };
        }
        await new Promise((resolve) => setTimeout(resolve, 100));
      }
      throw new DomainError("COMMAND_REJECTED", "Board did not confirm model activation and inference self-test", 409);
    } finally {
      this.updating = false;
      if (wasRunning) await this.sendCommand("START_INSPECTION");
    }
  }
  async restartInference() {
    await this.sendCommand("CAMERA_ONLY", 0);
    return this.sendCommand("START_INSPECTION");
  }
  getCurrentModel(): string | null {
    return this.state.reportedState.modelVersion ?? null;
  }
'''+s[end:]
p.write_text(s)
