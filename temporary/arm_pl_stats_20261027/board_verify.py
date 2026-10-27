from __future__ import print_function
import json, urllib.request, subprocess, os

def sh(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode('utf8', 'replace').strip()
    except Exception as exc:
        return 'ERR:' + str(exc)

def get(url, timeout=10):
    op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return json.loads(op.open(url, timeout=timeout).read().decode('utf8'))

st = get('http://127.0.0.1:8877/state')
def pick(d, *keys):
    out = {}
    for k in keys:
        if k in d:
            out[k] = d[k]
    return out
print('EXP_STATE_TOP ' + ','.join(sorted(st.keys())))
print('EXP_STATE_SEL ' + json.dumps(pick(st, 'ok', 'mode', 'product', 'model', 'running', 'paused', 'production', 'preview', 'error', 'lastError', 'service', 'services', 'version', 'time')))
dev = st.get('device') or {}
print('EXP_STATE_DEVICE ' + json.dumps(pick(dev, 'preview', 'frame', 'seq', 'fps', 'width', 'height', 'model', 'product', 'production', 'error'), default=str)[:1500])
print('EXP_GOVERNOR ' + sh("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor") + ' cpu1=' + sh("cat /sys/devices/system/cpu/cpu1/cpufreq/scaling_governor"))
print('EXP_CPUINFO ' + sh("grep -c ^processor /proc/cpuinfo") + ' ' + sh("grep 'cpu MHz' /proc/cpuinfo | head -2 | tr '\n' ' '"))
print('EXP_LSMOD_VISION ' + sh("lsmod | grep -c vision_fb"))
print('EXP_SLCR ' + sh("devmem 0xf800000c 32") + ' fclk0=' + sh("devmem 0xf8000170 32"))
print('EXP_SERVICES ' + sh("ps | grep -E 'vision-(engine|panel|manager)' | grep -v grep | awk '{print $5\"|\"$6}' | tr '\n' ' '"))
print('EXP_MMC_ERRORS ' + sh("dmesg | grep -ci 'mmc0.*error'") + ' sd_errors_total=' + sh("dmesg | grep -ci 'I/O error'"))
print('EXP_TMPFS ' + sh("df -h /run | tail -1"))
print('EXP_RESTORED ' + sh("ls -l /run/armpl_restore_stamp 2>/dev/null | wc -l") + ' log_tail=' + sh("tail -3 /run/armpl_board.log | tr '\n' ';'"))
