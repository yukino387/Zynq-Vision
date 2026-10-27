from __future__ import print_function
import json, urllib.request, subprocess, time

def sh(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode('utf8','replace').strip()
    except Exception as exc:
        return 'rc!=0'

def get(url, timeout=10):
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return json.loads(op.open(url, timeout=timeout).read().decode('utf8'))

print('EXP_PIDS engine=' + sh("pidof vision-engine") + ' panel=' + sh("pidof vision-panel") + ' manager=' + sh("pidof vision-manager"))
a = get('http://127.0.0.1:8877/state')
time.sleep(2.0)
b = get('http://127.0.0.1:8877/state')
print('EXP_FRESH %s frameId %s -> %s (advancing=%s) paused=%s error=%r syncError=%r' % (a.get('fresh'), a.get('frameId'), b.get('frameId'), a.get('frameId') != b.get('frameId'), b.get('paused'), b.get('error'), b.get('syncError')))
last = b.get('last') or {}
print('EXP_LAST ' + json.dumps({k: last.get(k) for k in ('frameId','ts','count','detections','model','ms','latencyMs') if k in last})[:600])
print('EXP_COUNTS ' + json.dumps(b.get('counts'))[:200])
print('EXP_MMC ' + str(sh("dmesg | grep -ci 'mmc0: error'")) + ' | io_err=' + str(sh("dmesg | grep -ci 'I/O error'")) + ' | last_mmc=' + sh("dmesg | grep mmc0 | tail -1 | cut -c1-100"))
print('EXP_UPTIME ' + sh('cat /proc/uptime') + ' | mode=' + sh('cat /proc/cmdline | cut -c1-90'))
print('EXP_TS ' + time.strftime('%Y-%m-%dT%H:%M:%S'))
