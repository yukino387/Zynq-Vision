from __future__ import print_function
import subprocess, hashlib, json
def sh(cmd):
    try:
        return subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode('utf8','replace').strip()
    except Exception:
        return 'rc!=0'
print('EXP_PS ' + sh("ps | grep -i vision | grep -v grep | sed 's/  */ /g' | cut -c1-120 | tr '\n' '|'"))
print('EXP_INITTAB ' + sh("grep -c . /etc/inittab") + ' lines; vision_entries=[' + sh("grep vision /etc/inittab | tr '\n' ';'") + ']')
print('EXP_MOUNT ' + sh("mount | grep -c 'inittab'") + ' bind mounts of inittab')
h = lambda p: hashlib.sha256(open(p,'rb').read()).hexdigest()
for p in ('/boot/BOOT.bin','/usr/local/bin/vision-panel','/usr/local/bin/vision-engine','/var/lib/vision/model/model.bin','/var/lib/vision/product.json','/etc/inittab'):
    print('EXP_SHA %s %s' % (p, h(p)))
print('EXP_RUNSTATE ' + sh("ls /run | tr '\n' ' '")[:400])
print('EXP_INITTAB_BAK ' + sh("ls -l /etc/inittab* 2>/dev/null | tr '\n' '|'"))
