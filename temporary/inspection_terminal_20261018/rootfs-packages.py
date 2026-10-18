import functools
import hashlib
import json
import lzma
from pathlib import Path
import re
import subprocess

root=Path('/workspace/temporary/inspection_terminal_20261018/ubuntu-arm')
database={}
for suite in ['noble','noble-updates','noble-security']:
    subprocess.run(['gpgv','--keyring','/usr/share/keyrings/ubuntu-archive-keyring.gpg',str(root/(suite+'.InRelease'))],check=True)
    release=root.joinpath(suite+'.InRelease').read_text()
    expected=re.search(r'^ ([a-f0-9]{64})\s+\d+ main/binary-armhf/Packages.xz$',release,re.M).group(1)
    data=root.joinpath(suite+'.Packages.xz').read_bytes()
    assert hashlib.sha256(data).hexdigest()==expected
    for block in lzma.decompress(data).decode().split('\n\n'):
        fields=dict(line.split(': ',1) for line in block.splitlines() if ': ' in line and not line.startswith(' '))
        if 'Package' in fields and 'Filename' in fields: database.setdefault(fields['Package'],[]).append(fields)

def compare(a,b):
    if a['Version']==b['Version']: return 0
    return 1 if subprocess.run(['dpkg','--compare-versions',a['Version'],'gt',b['Version']]).returncode==0 else -1

chosen={}
def choose(name):
    if name in chosen:return
    if name not in database:
        providers=[n for n,items in database.items() if any(name in re.sub(r'\([^)]*\)','',item.get('Provides','')).replace(' ','').split(',') for item in items)]
        if not providers: raise RuntimeError('Missing dependency '+name)
        name=providers[0]
    item=max(database[name],key=functools.cmp_to_key(compare));chosen[name]=item
    for group in (item.get('Pre-Depends','')+','+item.get('Depends','')).split(','):
        alternatives=[re.sub(r'\([^)]*\)','',part).strip().split(':')[0].strip() for part in group.split('|')]
        options=[part for part in alternatives if part]
        if not options:continue
        choose(next((part for part in options if part in database),options[0]))

for package in ['busybox-static','python3-minimal','libpython3.12-stdlib','libstdc++6']: choose(package)
root.joinpath('packages.json').write_text(json.dumps([{'name':item['Package'],'version':item['Version'],'url':'https://ports.ubuntu.com/ubuntu-ports/'+item['Filename'],'file':Path(item['Filename']).name,'sha256':item['SHA256']} for item in chosen.values()]))
print('Signed Ubuntu ARM package set resolved:',len(chosen))
