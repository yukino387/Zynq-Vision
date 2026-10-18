from pathlib import Path
p=Path('apps/mobile/vite.config.ts');s=p.read_text(encoding='utf-8');needle='  server: {';assert needle in s;s=s.replace(needle,'  optimizeDeps: { exclude: ["@vision/shared"] },\n'+needle,1);p.write_bytes(s.encode())
