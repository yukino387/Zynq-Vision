from pathlib import Path
import base64, hashlib, json, os, struct, time, zlib

assert os.stat('/').st_dev == os.makedev(179, 2), 'Panel must run from persistent SD root'
names = {str(p.parent.parent.name): p.read_text().strip() for p in Path('/sys/class/input').glob('event*/device/name')}
mouse = next(node for node, name in names.items() if name == 'Logitech USB Receiver Mouse')
def has_tab(node):
    words = (Path('/sys/class/input')/node/'device/capabilities/key').read_text().split()
    return bool(sum(int(word,16) << (32*i) for i,word in enumerate(reversed(words))) & (1<<15))
keyboard = next(node for node, name in names.items() if name.startswith('2.4G Dongle') and has_tab(node))
mouse_fd = os.open('/dev/input/'+mouse, os.O_WRONLY)
keyboard_fd = os.open('/dev/input/'+keyboard, os.O_WRONLY)

def event(fd, kind, code, value):
    os.write(fd, struct.pack('<iiHHi', 0, 0, kind, code, value))
def move(x, y):
    event(mouse_fd,2,0,x);event(mouse_fd,2,1,y);event(mouse_fd,0,0,0);time.sleep(.25)
def click():
    event(mouse_fd,1,272,1);event(mouse_fd,0,0,0);time.sleep(.15)
    event(mouse_fd,1,272,0);event(mouse_fd,0,0,0);time.sleep(.3)
def tab():
    event(keyboard_fd,1,15,1);event(keyboard_fd,0,0,0);time.sleep(.15)
    event(keyboard_fd,1,15,0);event(keyboard_fd,0,0,0);time.sleep(.3)
def frame():
    with open('/dev/fb0','rb',buffering=0) as stream: raw=stream.read(1280*720*4)
    assert len(raw) == 1280*720*4
    return raw
def pixel(raw,x,y): return struct.unpack_from('<I',raw,(y*1280+x)*4)[0]&0xffffff
def roi(raw,x1,y1,x2,y2):
    return b''.join(raw[(y*1280+x1)*4:(y*1280+x2)*4] for y in range(y1,y2))

try:
    move(-50000,-50000);move(100,450)
    first=frame();assert pixel(first,107,457)==0xffffff, 'Cursor invisible after top/left overshoot'
    move(50000,50000)
    assert pixel(frame(),107,457)!=0xffffff, 'Old cursor pixels remain'
    move(-479,-29)
    assert pixel(frame(),807,697)==0xffffff, 'Cursor does not recover from bottom/right overshoot'
    move(-650,-578)  # (150,112): job dropdown in the XP toolbar.
    closed=frame();click();opened=frame()
    changed=sum(a!=b for a,b in zip(roi(closed,26,140,524,180),roi(opened,26,140,524,180)))
    assert changed>500, 'XP dropdown did not open on click'
    move(950,480);click()  # Close without selecting or creating any job.
    before=frame();tab();after=frame()
    focus_changed=sum(a!=b for a,b in zip(roi(before,20,87,1020,141),roi(after,20,87,1020,141)))
    assert focus_changed>100, 'Keyboard Tab did not change focus in the XP toolbar'
    move(-1100,-592);move(1190,640)  # Leave the cursor in the status bar.
    final=frame()
    panel=Path('/usr/local/bin/vision-panel')
    digest=hashlib.file_digest(panel.open('rb'),'sha256').hexdigest()
    assert digest == Path('/tmp/panel-expected-sha256').read_text().strip()
    print('XP_UI_FRAME '+base64.b64encode(zlib.compress(final,1)).decode(),flush=True)
    print('XP_UI_RESULT '+json.dumps({'panelSha256':digest,'persistentSdRoot':True,
        'mouseDevice':mouse,'keyboardDevice':keyboard,'cursorVisible':True,'edgeRecovery':True,
        'oldCursorPixelsCleared':True,'dropdownClickVerified':True,'dropdownRoiChangedBytes':changed,
        'keyboardTabVerified':True,'keyboardFocusChangedBytes':focus_changed,
        'frameSha256':hashlib.sha256(final).hexdigest(),'physicalHandTestAfterStyleChange':False}),flush=True)
finally:
    os.close(mouse_fd);os.close(keyboard_fd)
