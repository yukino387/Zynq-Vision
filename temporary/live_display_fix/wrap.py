from pathlib import Path
p=Path('temporary/live_display_fix/check_live.ts');s=p.read_text(encoding='utf-8');pos=s.index('const response');s=s[:pos]+'async function main(){\n'+s[pos:]+'\n}\nmain().catch(error=>{console.error(error);process.exitCode=1;});\n';p.write_bytes(s.encode())
