from pathlib import Path
import base64, hashlib, json, re, sys, zlib

task = Path(__file__).resolve().parent
repository = task.parents[1]

if sys.argv[1] == 'upload':
    source = Path(sys.argv[2])
    payload = base64.b64encode(source.read_bytes()).decode()
    target = '/tmp/xp-'+source.stem+'.b64'
    lines = ['rm -f '+target]
    lines += ['echo '+payload[i:i+180]+' >> '+target for i in range(0, len(payload), 180)]
    lines += ['python3 -c "import base64;exec(compile(base64.b64decode(open(\''+target+'\').read()),\''+source.name+'\',\'exec\'))"']
    with (task/'uart.commands').open('a', encoding='utf-8', newline='\n') as stream:
        stream.write('\n'.join(lines)+'\n')
    print('Queued script:', source.name, len(lines), 'bounded UART lines')
elif sys.argv[1] == 'expect':
    digest = hashlib.file_digest((repository/'camera/terminal/build/arm/vision-panel').open('rb'), 'sha256').hexdigest()
    with (task/'uart.commands').open('a', encoding='utf-8', newline='\n') as stream:
        stream.write('echo '+digest+' > /tmp/panel-expected-sha256\n')
    print('Expected panel:', digest)
elif sys.argv[1] == 'collect':
    from PIL import Image
    log = (task/'uart.bin').read_bytes().decode(errors='replace')
    evidence = json.loads(re.findall(r'^XP_UI_RESULT (.+)\r?$', log, re.M)[-1])
    update = json.loads(re.findall(r'^PANEL_UPDATE (.+)\r?$', log, re.M)[-1])
    raw = zlib.decompress(base64.b64decode(re.findall(r'^XP_UI_FRAME (.+)\r?$', log, re.M)[-1]))
    assert len(raw) == 1280*720*4
    assert hashlib.sha256(raw).hexdigest() == evidence['frameSha256']
    assert evidence['panelSha256'] == update['sha256']
    Image.frombytes('RGB', (1280,720), raw, 'raw', 'BGRX').save(task/'board-xp.png')
    evidence['panelUpdate'] = update
    evidence['armRenderedStates'] = ['idle', 'review (synthetic fixture)', 'error']
    assert (task/'render.exit').read_text().strip() == '0'
    (task/'verification.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
