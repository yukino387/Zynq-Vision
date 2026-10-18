import zipfile, pathlib, json, hashlib
root=pathlib.Path(__file__).resolve().parent
apk=root/'delivery'/'视觉采样-v0.2.0.apk'
with zipfile.ZipFile(apk) as z:
    if z.testzip() is not None:raise RuntimeError('APK ZIP integrity failure')
    manifests=[n for n in z.namelist() if n.endswith('www/manifest.json')]
    if len(manifests)!=1:raise RuntimeError('Unexpected app resource manifest count')
    manifest=json.loads(z.read(manifests[0]))
    prefix=manifests[0].removesuffix('manifest.json')
    local=root.parent.parent/'apps/mobile/dist/build/app-plus'
    compare=[]
    for name in ['app-service.js','app-config-service.js','app-config.js','app.css']:
        if prefix+name in z.namelist() and (local/name).exists():
            matches=z.read(prefix+name)==(local/name).read_bytes()
            compare.append({'file':name,'matchesBuildOutput':matches})
            if not matches:raise RuntimeError('APK does not match compiled output: '+name)
    if manifest.get('id')!='__UNI__05C60CA' or manifest.get('version',{}).get('name')!='0.2.0':raise RuntimeError('APK metadata mismatch')
    report={'bytes':apk.stat().st_size,'sha256':hashlib.sha256(apk.read_bytes()).hexdigest(),'appid':manifest.get('id'),'version':manifest.get('version'),'nativeLibraries':sorted(set(n.split('/')[1] for n in z.namelist() if n.startswith('lib/') and n.endswith('.so'))),'comparedResources':compare,'zipIntegrity':'passed'}
    (root/'apk-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
