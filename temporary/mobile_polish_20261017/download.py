import urllib.request, pathlib, json, time
out=pathlib.Path(__file__).resolve().parent/'delivery'
url='https://app.liuyingyong.cn/build/download/d6989830-ca3d-11f1-a893-073eb2be06f9'
start=time.monotonic()
with urllib.request.urlopen(url,timeout=45) as response, (out/'download-fast.apk').open('wb') as target:
    (out/'download-url.txt').write_text(response.url,encoding='utf-8')
    print(json.dumps({'bytes':response.headers.get('Content-Length'),'type':response.headers.get('Content-Type')},ensure_ascii=False),flush=True)
    total=0
    while True:
        block=response.read(1024*1024)
        if not block:break
        target.write(block)
        total+=len(block)
        if total%(10*1024*1024)==0:print(f'{total//1024//1024} MiB downloaded',flush=True)
print(json.dumps({'downloaded':total,'seconds':round(time.monotonic()-start,1)}),flush=True)
