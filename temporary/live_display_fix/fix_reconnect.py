from pathlib import Path
p=Path('apps/server/src/devices/zynq.ts');s=p.read_text(encoding='utf-8');s=s.replace('  private previewOnly = false;','  private previewOnly = false;\n  private previewEnabled = false;\n  private polling = false;',1)
a='''      this.timer = setInterval(() => {
        void this.request(0).catch((e) => {
          this.state.error = String(e);
        });
      }, 3000);'''
b='''      this.timer = setInterval(() => {
        if (this.polling) return;
        this.polling = true;
        void this.request(0)
          .then(async () => {
            // A board reboot clears its UDP destination but status reads still
            // succeed. Re-register preview only when that subscription is lost.
            if (!this.owned || this.previewEnabled || this.updating) return;
            this.latest = null;
            this.assembler.clear();
            await this.request(1);
            await this.modelRpc(0)
              .then((reply) => this.updateModelState(reply))
              .catch(() => undefined);
          })
          .catch((e) => {
            this.state.error = String(e);
          })
          .finally(() => {
            this.polling = false;
          });
      }, 3000);'''
assert a in s;s=s.replace(a,b,1);s=s.replace('        this.previewOnly = Boolean(status.flags & 2);','        this.previewOnly = Boolean(status.flags & 2);\n        this.previewEnabled = Boolean(status.flags & 4);',1)
s=s.replace('    this.owned = false;\n    this.state.lastSeen', '    this.owned = false;\n    this.previewEnabled = false;\n    this.state.lastSeen',1);p.write_bytes(s.encode())
