#!/usr/bin/env python3
"""Local Linux monitoring and removable-media operations for the native panel."""
import collections
import concurrent.futures
import fcntl
import hashlib
import http.server
import json
import os
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from vision_auth import Authority, AuthError

STATE = Path('/var/lib/vision')
AUTH = Authority(STATE/'connection.json')
MEDIA = Path('/media/vision')
LOCK = threading.Lock()
SNAPSHOT = {}
PLATFORM = {'online': False, 'error': '', 'lastSuccess': None, 'deviceId': ''}
OPERATION = {'busy': False, 'id': 0, 'action': '', 'result': '', 'error': ''}
HISTORY = {'cpu': collections.deque(maxlen=60), 'memory': collections.deque(maxlen=60)}
POOL = concurrent.futures.ThreadPoolExecutor(max_workers=1)
HTTP = urllib.request.build_opener(urllib.request.ProxyHandler({}))
PREVIEW_PORT = 8879
PREVIEW_CACHE = {'at': 0.0, 'body': b''}
PREVIEW_LOCK = threading.Lock()
REFRESH = threading.Event()


def read(path, default='', limit=65536):
    try:
        with open(path, encoding='utf-8', errors='replace') as stream:
            return stream.read(limit).strip()
    except OSError:
        return default


def sync_directory(path):
    if os.name != 'posix':
        return
    descriptor = os.open(path, os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)


def engine(path='/state', payload=None, token=''):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request('http://127.0.0.1:8877'+path, data,
                                     {'Content-Type': 'application/json', 'Authorization': 'Bearer '+token})
    try:
        with HTTP.open(request, timeout=30 if path == "/model" else 3) as response:
            return json.loads(response.read(1024*1024))
    except urllib.error.HTTPError as exc:
        raise ValueError(json.loads(exc.read()).get('error', '检测服务操作失败')) from exc


def mounts():
    result = []
    for line in read('/proc/mounts', limit=256*1024).splitlines():
        columns = line.split()
        if len(columns) < 4:
            continue
        device, directory, kind, options = columns[:4]
        directory = re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), directory)
        if device.startswith('/dev/'):
            try:
                space = os.statvfs(directory)
                result.append({'device': device, 'path': directory, 'type': kind,
                               'readOnly': 'ro' in options.split(','),
                               'total': space.f_blocks*space.f_frsize,
                               'available': space.f_bavail*space.f_frsize,
                               'used': (space.f_blocks-space.f_bfree)*space.f_frsize})
            except OSError:
                pass
    return result


def usb_disks():
    result = []
    for path in sorted(Path('/sys/class/block').glob('sd*')):
        if not re.fullmatch(r'sd[a-z]+[0-9]+', path.name) or 'usb' not in str(path.resolve()):
            continue
        result.append({'device': '/dev/'+path.name,
                       'bytes': int(read(path/'size', '0'))*512,
                       'mounted': next((m['path'] for m in mounts() if m['device'] == '/dev/'+path.name), '')})
    return result


def media_roots():
    # Only mounted USB partitions are writable destinations. SD boot is import-only.
    return [Path(disk['mounted']).resolve() for disk in usb_disks() if disk['mounted']]


def allowed_path(value, export=False):
    path = Path(value).resolve(strict=True)
    roots = media_roots() + ([] if export else [Path('/boot/vision')])
    if not any(path == root or root in path.parents for root in roots):
        raise ValueError('请选择已挂载的 U 盘'+('目录' if export else '或启动分区作业包'))
    if export and not path.is_dir():
        raise ValueError('导出目标必须是目录')
    return path


def packages():
    rows = []
    for root in media_roots()+[Path('/boot/vision')]:
        if root.is_dir():
            # Restrict discovery to the root and its vision directory.
            for parent in (root, root/'vision'):
                if parent.is_dir():
                    for path in sorted(parent.glob('*.zip')):
                        if not path.is_symlink() and path.is_file():
                            rows.append({'path': str(path), 'name': path.name, 'bytes': path.stat().st_size})
    return rows[:100]


def jobs():
    try:
        inspection = engine()
    except Exception:
        inspection = {}
    connection = json.loads(read(STATE/'connection.json', '{}'))
    return {'items': [], 'packages': packages(), 'activeId': '',
            'model': inspection.get('model'), 'product': inspection.get('product'),
            'connections': [{'path':str(path),'name':str(path)} for root in media_roots()+[Path('/boot/vision')] for path in [root/'connection.json',root/'vision'/'connection.json'] if path.is_file() and not path.is_symlink()],
            'deviceId': connection.get('deviceId', ''), 'linked': bool(connection.get('server'))}


def save_json(path, document):
    temporary = path.with_name(path.name+'.next')
    fd = os.open(temporary, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(document, stream);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary, path)
    sync_directory(path.parent)


def platform_page(token):
    session = AUTH.status(token)
    connection = json.loads(read(STATE/'connection.json', '{}'))
    with LOCK:status = dict(PLATFORM)
    document = {'status': status, 'deviceId': connection.get('deviceId', ''), 'devices': [], 'jobs': []}
    if session['role'] != 'admin':
        return document
    devices = AUTH.platform_request(token, '/api/devices?pageSize=100')
    document['devices'] = [{'id': item['id'], 'name': item['name'], 'serialNumber': item['serialNumber']} for item in devices['items'] if item['type'] == 'ZYNQ']
    return document


def heartbeat_once():
    connection = json.loads(read(STATE/'connection.json', '{}'))
    if not connection:
        with LOCK:PLATFORM.update(online=False, error='请登录后绑定平台设备', deviceId='')
        return
    try:
        inspection = engine()
        with LOCK:sample = dict(SNAPSHOT)
        memory = sample.get('memory', {})
        total = memory.get('MemTotal', 0)
        pending_request = inspection.get('pendingRequestId') or None
        diagnostics = inspection.get('diagnostics', {})
        timing = ({'frameId': inspection.get('frameId', 0),
                   'captureMs': diagnostics.get('lastCaptureMs') or 0,
                   'prepareMs': diagnostics.get('hwPrepareMs') or 0,
                   'convMs': diagnostics.get('hwConvMs') or 0,
                   'forwardMs': diagnostics.get('hwForwardMs') or 0,
                   'postMs': diagnostics.get('hwPostMs') or 0,
                   'extractMs': diagnostics.get('hwExtractMs') or 0}
                  if diagnostics.get('lastCaptureMs') else None)
        payload = {'bootId': read('/proc/sys/kernel/random/boot_id'), 'uptime': float(read('/proc/uptime', '0').split()[0]),
                   'model': inspection.get('model'), 'product': inspection.get('product'),
                   'total': inspection.get('total', 0), 'counts': inspection.get('counts', {}),
                   'runTotal': inspection.get('runTotal', 0), 'runCounts': inspection.get('runCounts', {}),
                   'production': inspection.get('production', False),
                   'productionRunId': inspection.get('productionRunId') or None,
                   'passagePhase': inspection.get('passagePhase', 'STOPPED'),
                   'fps': (1000.0/diagnostics.get('lastCaptureMs'))
                          if diagnostics.get('lastCaptureMs') else None,
                   'timing': timing,
                   'paused': inspection.get('paused', True), 'fresh': inspection.get('fresh', False),
                   'pendingSync': inspection.get('pendingSync', 0), 'pendingRequestId': pending_request,
                   'last': inspection.get('last'), 'error': inspection.get('error', '')[:1000],
                   'syncError': inspection.get('syncError', '')[:1000],
                   'cpuPercent': sample.get('cpus', [{}])[0].get('percent') if sample.get('cpus') else None,
                   'memoryUsed': max(0, total-memory.get('MemAvailable', total)), 'memoryTotal': total}
        request = urllib.request.Request(connection['server']+'/api/terminal/heartbeat',json.dumps(payload).encode(),{'Content-Type':'application/json','Authorization':'Bearer '+connection['token']})
        with HTTP.open(request,timeout=3) as response:receipt=json.load(response)
        with LOCK:PLATFORM.update(online=True,error='',lastSuccess=receipt['receivedAt'],deviceId=connection['deviceId'])
    except Exception as exc:
        with LOCK:PLATFORM.update(online=False,error='平台连接或凭据异常：'+str(exc)[:180],deviceId=connection.get('deviceId',''))


def platform_sync():
    while True:
        try:heartbeat_once()
        except Exception as exc:
            with LOCK:PLATFORM.update(online=False,error='平台配置无效：'+str(exc)[:180])
        REFRESH.wait(5)
        REFRESH.clear()


def records(page=0, result=''):
    return engine('/records?'+urllib.parse.urlencode({'page': page, 'result': result}))


class Sampler:
    def __init__(self):
        self.cpu = {}
        self.process = {}
        self.net = {}
        self.when = None
        self.frames = None

    def sample(self):
        now = time.monotonic()
        elapsed = now-self.when if self.when is not None else None
        cpus = []
        total_delta = 0
        for line in read('/proc/stat').splitlines():
            fields = line.split()
            if not fields or not re.fullmatch(r'cpu[0-9]*', fields[0]):
                continue
            values = list(map(int, fields[1:9]))  # guest time is already included in user/nice.
            current = (sum(values), values[3]+values[4])
            previous = self.cpu.get(fields[0])
            usage = None
            if previous and current[0] > previous[0]:
                delta = current[0]-previous[0]
                usage = round(100*(1-(current[1]-previous[1])/delta), 1)
                if fields[0] == 'cpu':
                    total_delta = delta
            cpus.append({'name': fields[0], 'percent': usage})
            self.cpu[fields[0]] = current
        memory = {}
        for line in read('/proc/meminfo').splitlines():
            key, value = line.split(':', 1)
            if value.strip().endswith('kB'):
                memory[key] = int(value.split()[0])*1024
        processes = []
        next_process = {}
        for directory in Path('/proc').glob('[0-9]*'):
            try:
                stat = read(directory/'stat')
                closing = stat.rindex(')')
                fields = stat[closing+2:].split()
                ticks = int(fields[11])+int(fields[12])
                key = (directory.name, fields[19])  # PID and start time avoid PID reuse.
                previous = self.process.get(key)
                cpu = round(100*(ticks-previous)/total_delta, 1) if previous is not None and total_delta else None
                processes.append({'pid': int(directory.name), 'name': stat[stat.index('(')+1:closing],
                                  'state': fields[0], 'cpu': cpu,
                                  'memory': max(0, int(fields[21]))*os.sysconf('SC_PAGE_SIZE')})
                next_process[key] = ticks
            except (ValueError, IndexError, OSError):
                pass
        self.process = next_process
        processes.sort(key=lambda p: (p['cpu'] or 0, p['memory']), reverse=True)
        network = []
        for line in read('/proc/net/dev').splitlines()[2:]:
            name, values = line.split(':', 1)
            name = name.strip(); values = list(map(int, values.split()))
            previous = self.net.get(name)
            row = {'name': name, 'received': values[0], 'sent': values[8],
                   'rxErrors': values[2], 'txErrors': values[10],
                   'rxRate': max(0, (values[0]-previous[0])/elapsed) if previous and elapsed else None,
                   'txRate': max(0, (values[8]-previous[1])/elapsed) if previous and elapsed else None,
                   'carrier': read('/sys/class/net/'+name+'/carrier') == '1',
                   'speedMbps': read('/sys/class/net/'+name+'/speed', '—')}
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as channel:
                for key, request in (('address', 0x8915), ('netmask', 0x891b)):
                    try:
                        row[key] = socket.inet_ntoa(fcntl.ioctl(channel, request, struct.pack('256s', name.encode()[:15]))[20:24])
                    except OSError:
                        row[key] = ''
            network.append(row);self.net[name] = (values[0], values[8])
        temperatures = []
        for path in Path('/sys/class/thermal').glob('thermal_zone*/temp'):
            try:
                temperatures.append(float(read(path))/1000)
            except ValueError:
                pass
        if not temperatures:
            for path in Path('/sys/bus/iio/devices').glob('iio:device*/in_temp0_raw'):
                try:
                    parent = path.parent
                    temperatures.append((float(read(path))+float(read(parent/'in_temp0_offset')))*float(read(parent/'in_temp0_scale'))/1000)
                except ValueError:
                    pass
        services = {name: [p['pid'] for p in processes if p['name'] == name] for name in ('vision-engine', 'vision-panel')}
        services['vision-manager'] = [os.getpid()]
        try:
            inspection = engine()
            inspection['online'] = True
        except Exception:
            inspection = {'online': False}
        inference = inspection.get('diagnostics', {})
        count = inference.get('capturedFrames')
        fps = (count-self.frames)/elapsed if count is not None and self.frames is not None and count >= self.frames and elapsed else None
        self.frames = count
        self.when = now
        return {'monotonic': now, 'cpus': cpus, 'memory': memory,
                'uptime': float(read('/proc/uptime', '0').split()[0]),
                'load': read('/proc/loadavg').split()[:3], 'kernel': os.uname().release,
                'frequencyMHz': [int(read(p, '0'))/1000 for p in Path('/sys/devices/system/cpu').glob('cpu[0-9]*/cpufreq/scaling_cur_freq')],
                'temperatureC': round(temperatures[0], 1) if temperatures else None,
                'processes': processes[:40], 'processCount': len(processes), 'network': network,
                'mounts': mounts(), 'services': services, 'inspection': inspection, 'inferenceFps': fps}


def devices():
    usb = []
    for directory in Path('/sys/bus/usb/devices').glob('*'):
        if (directory/'idVendor').exists():
            usb.append({'port': directory.name, 'vendor': read(directory/'idVendor'),
                        'productId': read(directory/'idProduct'), 'name': read(directory/'product'),
                        'speedMbps': read(directory/'speed')})
    inputs = [{'node': '/dev/input/'+p.parent.parent.name, 'name': read(p)}
              for p in Path('/sys/class/input').glob('event*/device/name')]
    with LOCK:
        inspection = dict(SNAPSHOT.get('inspection', {}))
    visible = ''
    try:
        with open('/dev/fb0', 'rb', buffering=0) as stream:
            descriptor = bytearray(160)
            fcntl.ioctl(stream, 0x4600, descriptor, True)
            width, height = struct.unpack_from('II', descriptor)
            visible = str(width)+'×'+str(height)
    except OSError:
        pass
    return {'usb': usb, 'inputs': inputs,
            'camera': {'initialized': inspection.get('online', False) and inspection.get('diagnostics', {}).get('cameraInitialized', False),
                       'fresh': inspection.get('fresh', False), 'error': inspection.get('error', '')},
            'drivers': {name: Path('/sys/module/'+name).exists() for name in ('vision_accel', 'vision_fb')},
            'framebuffer': {'name': read('/sys/class/graphics/fb0/name'), 'visibleSize': visible, 'virtualSize': read('/sys/class/graphics/fb0/virtual_size'),
                            'bitsPerPixel': read('/sys/class/graphics/fb0/bits_per_pixel')},
            'mmc': [{'name': read(p/'name'), 'cid': read(p/'cid')} for p in Path('/sys/bus/mmc/devices').glob('*') if (p/'cid').exists()]}


def logs():
    reply = subprocess.run(['/bin/dmesg'], capture_output=True, text=True, errors='replace', timeout=3)
    if reply.returncode:
        raise ValueError(reply.stderr.strip() or '无法读取内核日志')
    return '\n'.join(reply.stdout.splitlines()[-160:])


def write_archive(destination, diagnostic=False):
    destination = allowed_path(destination, export=True)
    if diagnostic:
        files = []
    else:
        files = [p for p in (STATE/'records').glob('*') if p.is_file() and not p.is_symlink() and (p.suffix == '.json' or p.name.endswith('.json.ack'))]
    required = sum(p.stat().st_size for p in files)+16*1024*1024
    if shutil.disk_usage(destination).free < required:
        raise ValueError('U 盘剩余空间不足')
    stamp = str(time.time_ns())
    target = destination/('vision-'+('diagnostics-' if diagnostic else 'records-')+stamp+'.zip')
    temporary = target.with_suffix('.partial')
    try:
        with temporary.open('xb') as stream:
            with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
                if diagnostic:
                    with LOCK:
                        snapshot = dict(SNAPSHOT)
                    archive.writestr('system.json', json.dumps(snapshot, ensure_ascii=False, indent=2))
                    archive.writestr('devices.json', json.dumps(devices(), ensure_ascii=False, indent=2))
                    archive.writestr('kernel.log', logs())
                else:
                    for path in files:
                        archive.write(path, str(path.relative_to(STATE)))
            stream.flush();os.fsync(stream.fileno())
        temporary.rename(target)
        sync_directory(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return str(target)


def action(name, payload, token=''):
    if name == 'mount':
        node = payload['device']
        disk = next((row for row in usb_disks() if row['device'] == node), None)
        if disk is None:
            raise ValueError('不是可挂载的 USB 分区')
        if disk['mounted']:
            return disk['mounted']
        MEDIA.mkdir(parents=True, exist_ok=True)
        target = MEDIA/Path(node).name
        target.mkdir(exist_ok=True)
        subprocess.run(['/bin/mount', '-o', 'nodev,nosuid,noexec', node, str(target)], check=True, capture_output=True, timeout=15)
        return str(target)
    if name == 'unmount':
        path = allowed_path(payload['path'], export=True)
        if path not in media_roots():
            raise ValueError('只能卸载 U 盘挂载点')
        os.sync()
        subprocess.run(['/bin/umount', str(path)], check=True, capture_output=True, timeout=15)
        return '已卸载'
    if name == 'bind_online':
        identifier = payload['deviceId']
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', identifier):raise ValueError('设备编号无效')
        previous = json.loads(read(STATE/'connection.json', '{}'))
        if previous.get('deviceId') and previous['deviceId'] != identifier:raise ValueError('本机已绑定其他设备，不能在检测现场切换设备身份')
        if read(STATE/'panel-request'):raise ValueError('请先核对上一次检查')
        server = AUTH.status(token)['server']
        document = AUTH.platform_request(token, '/api/terminal/'+identifier+'/credential', {'confirm': True, 'server': server})
        if document.get('deviceId') != identifier or document.get('server') != server or not re.fullmatch(r'[a-f0-9]{64}',document.get('token','')):raise ValueError('平台绑定响应无效')
        save_json(STATE/'connection.json',document)
        heartbeat_once()
        return '设备已绑定平台'
    if name == 'connect':
        path = allowed_path(payload['path'])
        if path.name != 'connection.json' or path.stat().st_size > 4096:
            raise ValueError('请选择平台下载的 connection.json')
        document = json.loads(path.read_text())
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', document.get('deviceId', '')) or not re.fullmatch(r'[a-f0-9]{64}', document.get('token', '')):
            raise ValueError('连接配置无效')
        previous = json.loads(read(STATE/'connection.json', '{}'))
        if previous.get('deviceId') and previous['deviceId'] != document['deviceId']:
            raise ValueError('连接配置属于其他终端')
        AUTH.platform_device(token, document['server'], document['deviceId'])
        temporary = STATE/'connection.json.next'
        descriptor = os.open(temporary, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(document, stream);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary, STATE/'connection.json')
        sync_directory(STATE)
        return '平台连接配置已安装；检测记录将使用设备凭据同步'
    if name in ('export', 'diagnostics'):
        return write_archive(payload['path'], name == 'diagnostics')
    if name == 'sync':
        if not (STATE/'connection.json').exists():
            raise ValueError('尚未连接平台，请由管理员导入 connection.json')
        engine('/sync', {})
        return '已请求同步'
    if name in ('reboot', 'poweroff'):
        if payload.get('confirmed') is not True:
            raise ValueError('操作未确认')
        if read(STATE/'panel-request'):
            raise ValueError('存在未确认的检查记录')
        engine('/pause', {'paused': True})
        os.sync()
        def power():
            try:
                subprocess.run(['/sbin/'+name], check=True)
            except Exception as exc:
                with LOCK:
                    OPERATION.update(busy=False, error=str(exc))
        threading.Timer(3, power).start()
        return '正在重新启动' if name == 'reboot' else '正在关机'
    raise ValueError('未知操作')


def submit(name, payload, token=''):
    if name != 'sync':
        AUTH.require(token)
    if name not in {'mount', 'unmount', 'bind_online', 'connect', 'export', 'diagnostics', 'sync', 'reboot', 'poweroff'}:
        raise ValueError('未知操作')
    with LOCK:
        if OPERATION['busy']:
            raise ValueError('已有操作正在执行')
        OPERATION.update(busy=True, id=OPERATION['id']+1, action=name, result='', error='', jobId='')
        identifier = OPERATION['id']
    def run():
        try:
            result = action(name, payload, token)
            with LOCK:
                OPERATION.update(busy=name in ('reboot', 'poweroff'), result=result['message'] if isinstance(result, dict) else result, jobId=result.get('jobId', '') if isinstance(result, dict) else '')
        except Exception as exc:
            with LOCK:
                OPERATION.update(busy=False, error=str(exc))
    POOL.submit(run)
    return {'id': identifier}


def sampling():
    sampler = Sampler()
    next_sample = time.monotonic()
    last_slot = None
    while True:
        try:
            sample = sampler.sample()
            slot = int(time.monotonic())
            if last_slot is not None:
                for _ in range(min(60, max(0, slot-last_slot-1))):
                    HISTORY['cpu'].append(None);HISTORY['memory'].append(None)
            last_slot = slot
            cpus = sample.get('cpus', [])
            cpu = cpus[0].get('percent') if cpus else None
            memory = sample.get('memory', {})
            total = memory.get('MemTotal', 0)
            available = memory.get('MemAvailable', 0)
            HISTORY['cpu'].append(round(cpu, 1) if cpu is not None else None)
            HISTORY['memory'].append(round(100*(total-available)/total, 1) if total else None)
            sample['sampleTime'] = time.monotonic()
            sample['history'] = {'cpu': list(HISTORY['cpu']), 'memory': list(HISTORY['memory'])}
            with LOCK:
                SNAPSHOT.clear();SNAPSHOT.update(sample)
        except Exception as exc:
            with LOCK:
                SNAPSHOT['samplingError'] = str(exc)
        next_sample += 1
        if next_sample < time.monotonic():
            next_sample = time.monotonic()
        time.sleep(max(0, next_sample-time.monotonic()))


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, status, document):
        data = json.dumps(document, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status);self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)));self.end_headers();self.wfile.write(data)

    def token(self):
        header = self.headers.get('Authorization', '')
        return header[7:] if header.startswith('Bearer ') else ''

    def do_GET(self):
        try:
            path = urllib.parse.urlsplit(self.path)
            if path.path == '/auth/session':
                self.reply(200, AUTH.status(self.token()));return
            if path.path == '/system':
                with LOCK:
                    body = dict(SNAPSHOT);body['operation'] = dict(OPERATION)
                body['session'] = AUTH.status(self.token())
                with LOCK:body['platform'] = dict(PLATFORM)
            elif path.path == '/platform':
                body = platform_page(self.token())
            elif path.path == '/devices':
                body = devices()
            elif path.path == '/storage':
                body = {'mounts': mounts(), 'usb': usb_disks()}
            elif path.path == '/jobs':
                body = jobs()
            elif path.path == '/records':
                query = urllib.parse.parse_qs(path.query)
                page = max(0, min(1000000, int(query.get('page', ['0'])[0])))
                body = records(page, query.get('result', [''])[0])
            elif path.path == '/logs':
                body = {'text': logs()}
            else:
                self.reply(404, {'error': '接口不存在'});return
            self.reply(200, body)
        except AuthError as exc:
            self.reply(exc.status, {'error': str(exc)})
        except Exception as exc:
            self.reply(409, {'error': str(exc)})

    def do_POST(self):
        try:
            if self.path == '/refresh':
                REFRESH.set();self.reply(200, {'queued': True});return
            length = int(self.headers.get('Content-Length', '0'))
            if length < 2 or length > 4096 or self.path not in {'/action', '/auth/login', '/auth/logout'}:
                raise ValueError('请求无效')
            document = json.loads(self.rfile.read(length))
            if not isinstance(document, dict):
                raise ValueError('请求无效')
            if self.path.startswith('/auth/'):
                self.reply(200, AUTH.request(self.path, document, self.token()));return
            self.reply(202, submit(document['action'], document.get('payload', {}), self.token()))
        except AuthError as exc:
            self.reply(exc.status, {'error': str(exc)})
        except Exception as exc:
            self.reply(409, {'error': str(exc)})


def write_bytes(path, data):
    temporary = path.with_name(path.name+'.next')
    fd = os.open(temporary, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data);stream.flush();os.fsync(stream.fileno())
    os.replace(temporary, path)
    sync_directory(path.parent)


def install_model(command):
    connection = json.loads(read(STATE/'connection.json', '{}'))
    if not connection.get('server'):
        raise ValueError('请先绑定平台')
    current = engine()
    if current.get('production') and command.get('confirm') is not True:
        raise ValueError('请先停止自动检测并确认当前件已处理')
    if current.get('pendingRequestId') or read(STATE/'panel-request'):
        raise ValueError('请先核对未确认保存的记录')
    if current.get('production'):
        engine('/production', {'enabled': False})
    identifier = command.get('modelId')
    if not isinstance(identifier, str) or not identifier:
        raise ValueError('模型编号无效')
    request = urllib.request.Request(connection['server']+'/api/terminal/model/'+urllib.parse.quote(identifier),
                                     headers={'Authorization': 'Bearer '+connection['token']})
    with HTTP.open(request, timeout=60) as response:
        data = response.read()
    if len(data) != 6416360:
        raise ValueError('模型文件大小不正确')
    if hashlib.sha256(data).hexdigest() != command.get('weightsSha256'):
        raise ValueError('模型文件摘要不匹配')
    directory = STATE/'model'
    directory.mkdir(parents=True, exist_ok=True)
    target = directory/'model.bin'
    backup = target.read_bytes() if target.exists() else None
    descriptor = {'formatVersion': 1, 'id': identifier,
                  'version': command.get('modelVersion'),
                  'payloadSha256': command.get('modelPayloadSha256'),
                  'weightsSha256': command.get('weightsSha256'),
                  'manifest': command.get('manifest'),
                  'classes': command.get('classes'),
                  'installedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    try:
        write_bytes(target, data)
        return engine('/model', descriptor)
    except Exception:
        if backup is not None:
            write_bytes(target, backup)
        else:
            target.unlink(missing_ok=True)
        raise


def install_product(command):
    current = engine()
    if current.get('production') and command.get('confirm') is not True:
        raise ValueError('请先停止自动检测并确认当前件已处理')
    if current.get('pendingRequestId') or read(STATE/'panel-request'):
        raise ValueError('请先核对未确认保存的记录')
    if current.get('production'):
        engine('/production', {'enabled': False})
    descriptor = {'id': command.get('planId'), 'name': command.get('planName'),
                  'version': command.get('planVersion'), 'rules': command.get('rules'),
                  'acceptance': command.get('acceptance'),
                  'assignedAt': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
    return engine('/product', descriptor)


class PreviewHandler(http.server.BaseHTTPRequestHandler):
    """Workbench bridge; control and sampling validate the bound platform session."""

    def platform_actor(self):
        connection = json.loads(read(STATE/'connection.json', '{}'))
        authorization = self.headers.get('Authorization', '')
        if not authorization.startswith('Bearer ') or not connection.get('server'):
            raise ValueError('请先登录平台')
        request = urllib.request.Request(connection['server']+'/api/auth/me', headers={'Authorization': authorization})
        with HTTP.open(request, timeout=3) as response:actor = json.load(response)
        return actor

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        try:
            actor = self.platform_actor()
            role = actor.get('role')
            length = int(self.headers.get('Content-Length', '0'))
            if length < 2 or length > 1048576:raise ValueError('请求无效')
            command = json.loads(self.rfile.read(length))
            if path == '/control':
                if role not in ('ADMIN', 'ENGINEER', 'OPERATOR'):
                    self.reply(403, b'Forbidden');return
                kind = command.get('type')
                if kind == 'START_INSPECTION':result = engine('/production', {'enabled': True})
                elif kind == 'STOP_INSPECTION':result = engine('/production', {'enabled': False})
                elif kind == 'CHECK_ONE':
                    identifier = command.get('requestId')
                    if not isinstance(identifier, str) or not re.fullmatch(r'[0-9a-f-]{36}', identifier):
                        raise ValueError('检查编号无效')
                    result = engine('/check', {'requestId': identifier})
                elif kind in ('GET_STATUS', 'CONNECT'):result = engine()
                else:raise ValueError('当前设备不支持该控制操作')
                if kind in ('START_INSPECTION', 'STOP_INSPECTION', 'CHECK_ONE'):
                    REFRESH.set()
                self.reply(200, json.dumps(result).encode());return
            if path == '/runtime/model':
                if role != 'ADMIN':
                    self.reply(403, b'Forbidden');return
                result = install_model(command)
                REFRESH.set()
                self.reply(200, json.dumps(result).encode());return
            if path == '/runtime/product':
                if role not in ('ADMIN', 'ENGINEER'):
                    self.reply(403, b'Forbidden');return
                result = install_product(command)
                REFRESH.set()
                self.reply(200, json.dumps(result).encode());return
            self.reply(404, b'Unknown command')
        except urllib.error.HTTPError as exc:
            self.reply(exc.code if exc.code in (401,403) else 409, b'Platform authorization failed')
        except Exception as exc:
            self.reply(409, json.dumps({'error': str(exc)}, ensure_ascii=False).encode())

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path in ('/capture', '/preview'):
            try:
                if path == '/capture':self.platform_actor()
                target = 'http://127.0.0.1:8877/frame'
                if path == '/preview':
                    after = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('after', [''])[0]
                    if after.isdigit():target += '?after=' + after
                with HTTP.open(target, timeout=2) as response:body = response.read()
                self.reply(200, body)
            except urllib.error.HTTPError as exc:self.reply(exc.code if exc.code in (401,403) else 409, b'Capture unavailable')
            except Exception as exc:self.reply(409, json.dumps({'error': str(exc)}, ensure_ascii=False).encode())
            return
        if path != '/frame':
            self.send_error(404);return
        now = time.monotonic()
        with PREVIEW_LOCK:
            if now - PREVIEW_CACHE['at'] < 0.25 and PREVIEW_CACHE['body']:
                self.reply(200, PREVIEW_CACHE['body']);return
        try:
            with HTTP.open('http://127.0.0.1:8877/frame', timeout=1) as response:
                body = response.read()
            if len(body) < 4:raise ValueError('Invalid frame')
            metadata = struct.unpack_from('<I', body, 0)[0]
            body = body[4+metadata:]
            if not body:raise ValueError('Empty frame')
            with PREVIEW_LOCK:
                PREVIEW_CACHE['at'] = now
                PREVIEW_CACHE['body'] = body
            self.reply(200, body)
        except urllib.error.HTTPError as exc:
            self.reply(exc.code, exc.read()[:200] or b'No current frame')
        except Exception:
            self.reply(503, b'Preview unavailable')

    def reply(self, status, body):
        self.send_response(status)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


if __name__ == '__main__':
    os.sched_setaffinity(0, {0})
    STATE.mkdir(parents=True, exist_ok=True)
    lock_stream = (STATE/'manager.lock').open('a')
    fcntl.flock(lock_stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
    threading.Thread(target=sampling, daemon=True).start()
    threading.Thread(target=platform_sync, daemon=True).start()
    preview = http.server.ThreadingHTTPServer(('0.0.0.0', PREVIEW_PORT), PreviewHandler)
    threading.Thread(target=preview.serve_forever, daemon=True).start()
    http.server.ThreadingHTTPServer(('127.0.0.1', 8878), Handler).serve_forever()
