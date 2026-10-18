import json,urllib.request
from pathlib import Path
url='https://api.github.com/repos/winthegame259/steel-surface-defect-detection/releases/latest'
request=urllib.request.Request(url,headers={'User-Agent':'IoT-Vision-Compatibility-Check'})
with urllib.request.urlopen(request,timeout=30) as response: data=json.load(response)
Path('temporary/online_weight_trial/public_release.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'tag':data['tag_name'],'url':data['html_url'],'assets':[{'name':a['name'],'bytes':a['size'],'download':a['browser_download_url']} for a in data['assets']]},ensure_ascii=False))
