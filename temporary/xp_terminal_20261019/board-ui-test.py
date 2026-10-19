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

def go(x,y):
    move(-50000,-50000);move(x,y)
def screenshot(marker, raw):
    print(marker+' '+base64.b64encode(zlib.compress(raw,1)).decode(),flush=True)
def visible():
    return pixel(frame(),100,300)==0

def drag(dx,dy):
    event(mouse_fd,1,272,1);event(mouse_fd,0,0,0);time.sleep(.1)
    move(dx,dy);event(mouse_fd,1,272,0);event(mouse_fd,0,0,0);time.sleep(.4)

try:
    go(100,650)
    first=frame();assert pixel(first,101,653)==0xffffff and pixel(first,100,650)==0, 'XP arrow is invisible'
    move(50000,50000)
    assert pixel(frame(),101,653)!=0xffffff, 'Old cursor pixels remain'
    move(-479,-19)
    assert pixel(frame(),801,703)==0xffffff, 'Cursor does not recover from bottom/right overshoot'
    go(200,95)
    closed=frame();click();opened=frame()
    changed=sum(a!=b for a,b in zip(roi(closed,86,113,455,142),roi(opened,86,113,455,142)))
    assert changed>500, 'Dropdown did not open on click'
    go(900,500);click()
    before=frame();tab();after=frame()
    focus_changed=sum(a!=b for a,b in zip(roi(before,450,78,760,116),roi(after,450,78,760,116)))
    assert focus_changed>100, 'Keyboard Tab did not change focus'
    go(1215,36);click()
    assert pixel(frame(),10,100)!=0x3a6ea5, 'Maximize failed'
    go(1236,20);click()
    assert pixel(frame(),10,100)==0x3a6ea5, 'Restore failed'
    go(500,36);drag(20,10)
    assert pixel(frame(),25,100)==0x3a6ea5, 'Title drag failed'
    go(520,46);drag(-20,-10)
    assert pixel(frame(),25,100)!=0x3a6ea5, 'Title drag did not return the window'
    go(1192,36);click()
    assert not visible(), 'Minimize failed'
    desktop=frame();screenshot('XP_UI_DESKTOP',desktop)
    go(200,705);click();assert visible(), 'Taskbar restore failed'
    active=frame()
    go(1240,36);click();assert not visible(), 'Close failed'
    assert roi(active,112,694,312,718)!=roi(frame(),112,694,312,718), 'Closed task remains on taskbar'
    go(55,60)
    for _ in range(2):
        event(mouse_fd,1,272,1);event(mouse_fd,0,0,0);time.sleep(.05)
        event(mouse_fd,1,272,0);event(mouse_fd,0,0,0);time.sleep(.05)
    time.sleep(.4);assert visible(), 'Desktop double click failed'
    go(1192,36);click();assert not visible(), 'Window did not minimize before Start launch'
    go(50,705);click()
    assert pixel(frame(),220,582)==0xffffff, 'Start menu failed'
    menu_frame=frame()
    assert sum(pixel(menu_frame,x,y)<0x333333 for y in range(582,604) for x in range(25,180))>50, 'Start menu labels are missing'
    screenshot('XP_UI_START',frame())
    go(100,592);click();assert visible(), 'Start menu application launch failed'
    go(60,63);click()
    assert pixel(frame(),200,85)==0xffffff, 'File menu failed'
    go(900,500);click()
    go(1150,658)
    final=frame()
    panel=Path('/usr/local/bin/vision-panel')
    digest=hashlib.file_digest(panel.open('rb'),'sha256').hexdigest()
    assert digest == Path('/tmp/panel-expected-sha256').read_text().strip()
    print('XP_UI_FRAME '+base64.b64encode(zlib.compress(final,1)).decode(),flush=True)
    print('XP_UI_RESULT '+json.dumps({'panelSha256':digest,'persistentSdRoot':True,
        'mouseDevice':mouse,'keyboardDevice':keyboard,'cursorVisible':True,'edgeRecovery':True,
        'oldCursorPixelsCleared':True,'dropdownClickVerified':True,'dropdownRoiChangedBytes':changed,
        'keyboardTabVerified':True,'keyboardFocusChangedBytes':focus_changed,
        'maximizeRestoreVerified':True,'titleDragVerified':True,'minimizeTaskbarRestoreVerified':True,
        'closeVerified':True,'desktopDoubleClickVerified':True,'startMenuLaunchVerified':True,'fileMenuVerified':True,
        'frameSha256':hashlib.sha256(final).hexdigest(),'physicalHandTestAfterStyleChange':False}),flush=True)
finally:
    os.close(mouse_fd);os.close(keyboard_fd)
