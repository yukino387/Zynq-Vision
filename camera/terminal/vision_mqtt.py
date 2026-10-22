"""MQTT 5 input, inspection results and configurable actuator outputs."""
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import re
import threading
import time
import uuid


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(str(path)+'.next', os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf8') as stream:
        json.dump(value, stream, ensure_ascii=False);stream.flush();os.fsync(stream.fileno())
    os.replace(str(path)+'.next', path)


def field(document, name, default=None):
    for key in name.split('.'):
        if not isinstance(document, dict) or key not in document:return default
        document = document[key]
    return document


def render(value, context):
    if isinstance(value, dict):return {k: render(v, context) for k, v in value.items()}
    if isinstance(value, list):return [render(v, context) for v in value]
    if isinstance(value, str):
        if value.startswith('${') and value.endswith('}') and value.count('${') == 1:
            return field(context, value[2:-1], '')
        return re.sub(r'\$\{([\w.]+)\}', lambda m: str(field(context, m[1], '')), value)
    return value


DEFAULT = {'enabled': False, 'host': '', 'port': 1883, 'tls': False, 'username': '',
           'clientId': 'vision-terminal', 'prefix': 'vision/terminal', 'topics': {},
           'input': {'commandField': 'type', 'requestIdField': 'requestId', 'pieceIdField': 'pieceId', 'aliases': {}},
           'rules': []}


class MqttBridge:
    def __init__(self, root, engine):
        self.root, self.engine = Path(root), engine
        self.folder = self.root/'mqtt';self.folder.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock();self.messages = queue.Queue(maxsize=32)
        self.client = None;self.connected = False;self.session = '';self.error = '';self.revision = 0
        self.applied = -1;self.retry_at = 0;self.connected_ns = 0;self.last_state = '';self.last_total = None
        self.commands = self._load('commands');self.results = self._load('results');self.actions = self._load('actions')
        self.pending = {k for k, v in self.results.items() if not v.get('acked')}
        self.config = dict(DEFAULT)
        if (self.folder/'config.json').exists():self.config.update(json.loads((self.folder/'config.json').read_text()))
        self.baseline = None
        if (self.folder/'baseline.json').exists():self.baseline = set(json.loads((self.folder/'baseline.json').read_text()))
        self.known = {v['file'] for v in self.results.values()}
        self.boot_id = (Path('/proc/sys/kernel/random/boot_id').read_text().strip()
                        if Path('/proc/sys/kernel/random/boot_id').exists() else '')
        self.due = {};self.running = True;self.thread = None
        for action in self.actions.values():
            if action['status'] in ('SENT', 'ACCEPTED'):
                action.update(status='UNKNOWN', error='接入进程重启，动作未重发');self._save('actions', action['actionId'], action)
        for command in self.commands.values():
            if command['status'] == 'ACCEPTED':
                command.update(status='INTERRUPTED', error='接入进程重启，请确认工件');self._save('commands', command['requestId'], command)

    def _load(self, name):
        directory = self.folder/name;directory.mkdir(exist_ok=True)
        return {p.stem: json.loads(p.read_text()) for p in directory.glob('*.json')}

    @staticmethod
    def key(identifier):return hashlib.sha256(identifier.encode()).hexdigest()

    def _save(self, name, identifier, value):write_json(self.folder/name/(self.key(identifier)+'.json'), value)

    def topics(self):
        base = self.config['prefix']
        return {name: self.config.get('topics', {}).get(name) or base+'/'+name
                for name in ('command', 'reply', 'state', 'result', 'event', 'availability', 'capabilities')}

    def status(self):
        with self.lock:
            config = {k: v for k, v in self.config.items() if k != 'password'}
            config['hasPassword'] = bool(self.config.get('password'))
            return {'config': config, 'connected': self.connected, 'sessionId': self.session,
                    'error': self.error, 'topics': self.topics(),
                    'pendingResults': len(self.pending),
                    'actions': list(self.actions.values())[-10:], 'commands': list(self.commands.values())[-10:]}

    def configure(self, document):
        config = {**DEFAULT, **document};config.pop('hasPassword', None)
        if 'password' not in document:config['password'] = self.config.get('password', '')
        if config['enabled'] and not config['host']:raise ValueError('请填写 MQTT Broker 地址')
        if not 1 <= int(config['port']) <= 65535:raise ValueError('端口无效')
        topics = list(config.get('topics', {}).values())+[config['prefix']]
        topics += [r['topic'] for r in config['rules']]+[r.get('ackTopic', '') for r in config['rules']]
        if any(not isinstance(v, str) or '+' in v or '#' in v or '\x00' in v for v in topics):raise ValueError('请使用不含通配符的 Topic')
        own = {config.get('topics', {}).get(k) or config['prefix']+'/'+k for k in ('command', 'state', 'reply', 'result', 'event', 'availability', 'capabilities')}
        if len(own) != 7 or any(r['topic'] in own or r.get('ackTopic') in own for r in config['rules']):raise ValueError('输入、输出与外设 Topic 不能冲突')
        with self.lock:
            write_json(self.folder/'config.json', config);self.config = config;self.revision += 1
        return self.status()

    def start(self):
        self.thread = threading.Thread(target=self.run, daemon=True, name='mqtt-bridge');self.thread.start()

    def close(self):
        self.running = False
        if self.thread:self.thread.join(timeout=5)

    def publish(self, topic, document, retain=False, expiry=None):
        if not self.connected:return False
        from paho.mqtt.properties import Properties
        from paho.mqtt.packettypes import PacketTypes
        props = Properties(PacketTypes.PUBLISH)
        if expiry:props.MessageExpiryInterval = max(1, math.ceil(expiry/1000))
        info = self.client.publish(topic, json.dumps(document, ensure_ascii=False), qos=1, retain=retain, properties=props)
        return info.rc == 0

    def event(self, kind, **values):
        self.publish(self.topics()['event'], {'type': kind, **values})

    def _connect(self):
        if self.client:
            self.connected = False;self.client.disconnect();self.client.loop_stop();self.client = None
        self.applied = self.revision
        if not self.config['enabled']:return
        import paho.mqtt.client as mqtt
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.config['clientId'],
                             protocol=mqtt.MQTTv5, reconnect_on_failure=False)
        client.connect_timeout = 3;client.max_queued_messages_set(128);client.max_inflight_messages_set(20)
        if self.config['username']:client.username_pw_set(self.config['username'], self.config.get('password', ''))
        if self.config['tls']:client.tls_set()
        client.will_set(self.topics()['availability'], json.dumps({'online': False}), qos=1, retain=True)
        client.on_connect = self._on_connect;client.on_disconnect = self._on_disconnect;client.on_message = self._on_message
        self.client = client;self.retry_at = time.monotonic()+5
        client.connect_async(self.config['host'], int(self.config['port']), 20, clean_start=True);client.loop_start()

    def _on_connect(self, client, userdata, flags, reason, properties):
        if reason.is_failure:self.error = str(reason);return
        self.connected = True;self.error = '';self.session = str(uuid.uuid4());self.connected_ns = time.monotonic_ns();self.last_state = ''
        from paho.mqtt.subscribeoptions import SubscribeOptions
        options = SubscribeOptions(qos=1, retainAsPublished=True, retainHandling=2)
        topics = self.topics();client.subscribe(topics['command'], options=options)
        for topic in {r.get('ackTopic') for r in self.config['rules'] if r.get('ackTopic')}:client.subscribe(topic, options=options)
        self.publish(topics['availability'], {'online': True, 'sessionId': self.session}, True)
        self.publish(topics['capabilities'], {'protocol': 'MQTT5', 'topics': topics, 'commands': ['TRIGGER', 'START', 'STOP', 'GET_STATUS', 'GET_RESULT', 'ACK_RESULT'],
                     'sessionId': self.session, 'results': ['PASS', 'FAIL', 'REVIEW', 'ERROR']}, True)

    def _on_disconnect(self, client, userdata, flags, reason, properties):
        self.connected = False;self.retry_at = time.monotonic()+2
        with self.lock:
            for action in self.actions.values():
                if action['status'] in ('SENT', 'ACCEPTED'):
                    action.update(status='UNKNOWN', error='连接中断，动作未重发');self._save('actions', action['actionId'], action)

    def _on_message(self, client, userdata, message):
        if message.retain or len(message.payload)>16384:return
        try:self.messages.put_nowait((message.topic, json.loads(message.payload), time.monotonic()))
        except (ValueError, queue.Full):self.event('INPUT_REJECTED', reason='消息格式错误或忙碌')

    def _reply(self, document):self.publish(self.topics()['reply'], document)

    def command(self, body, received):
        mapping = self.config['input'];kind = field(body, mapping.get('commandField', 'type'))
        kind = mapping.get('aliases', {}).get(kind, kind)
        request = str(uuid.UUID(str(field(body, mapping.get('requestIdField', 'requestId')))))
        normalized = {'type': kind, 'requestId': request, 'pieceId': str(field(body, mapping.get('pieceIdField', 'pieceId'), '')),
                      'windowMs': body.get('windowMs', 500)}
        for key in ('productId', 'productVersion', 'resultId'):
            if key in body:normalized[key] = body[key]
        key = self.key(request);previous = self.commands.get(key)
        if previous:
            if previous['command'] != normalized:raise ValueError('requestId 参数冲突')
            self._reply(previous);return
        if kind in ('TRIGGER', 'START') and body.get('sessionId') != self.session:raise ValueError('sessionId 已失效，请读取当前 state')
        if time.monotonic()-received > 5:raise ValueError('命令已过期')
        document = {'requestId': request, 'status': 'ACCEPTED', 'command': normalized}
        self._save('commands', request, document);self.commands[key] = document
        try:
            if kind == 'TRIGGER':
                command = {k: v for k, v in normalized.items() if k in ('requestId', 'pieceId', 'windowMs', 'productId', 'productVersion')}
                job = self.engine('/inspect', command);document['status'] = job['status'];document['job'] = job
            elif kind in ('START', 'STOP'):
                document.update(status='COMPLETED', state=self.engine('/production', {'enabled': kind == 'START'}))
            elif kind == 'GET_STATUS':document.update(status='COMPLETED', state=self.engine(), sessionId=self.session)
            elif kind in ('GET_RESULT', 'ACK_RESULT'):
                result = self.results[self.key(str(body['resultId']))]
                if kind == 'ACK_RESULT':
                    result['acked'] = True;self.pending.discard(self.key(result['resultId']));self._save('results', result['resultId'], result)
                document.update(status='COMPLETED', result=result['message'])
            else:raise ValueError('未知命令')
        except Exception as exc:document.update(status='ERROR', error=str(exc))
        self._save('commands', request, document);self._reply(document)

    def receipt(self, topic, body):
        for rule in self.config['rules']:
            if rule.get('ackTopic') != topic:continue
            identifier = str(field(body, rule.get('ackIdField', 'actionId'), ''))
            action = self.actions.get(self.key(identifier))
            if not action or action['ruleId'] != rule['id'] or action['status'] not in ('SENT', 'ACCEPTED'):continue
            status = field(body, rule.get('ackStatusField', 'status'))
            if status == rule.get('ackSuccessValue', 'EXECUTED'):status = 'EXECUTED'
            if status not in ('ACCEPTED', 'EXECUTED', 'FAILED'):continue
            action.update(status=status, receipt=body);self._save('actions', identifier, action);self.event('ACTION_'+status, action=action)

    def _outputs(self, result, payload):
        for rule in self.config['rules']:
            if rule['when'] != result['result']:continue
            identifier = result['resultId']+':'+rule['id'];key = self.key(identifier)
            if key in self.actions:continue
            fresh = payload['bootId'] == self.boot_id and result.get('completedMonotonicNs')
            age = (time.monotonic_ns()-int(result['completedMonotonicNs']))/1e6 if fresh else float('inf')
            context = {**result, 'actionId': identifier};message = render(rule['payload'], context)
            message.setdefault('actionId', identifier);message.setdefault('pieceId', result.get('pieceId', ''))
            action = {'actionId': identifier, 'resultId': result['resultId'], 'ruleId': rule['id'], 'topic': rule['topic'],
                      'status': 'SENT' if self.connected and age < rule['expiryMs'] else 'SKIPPED',
                      'message': message, 'deadlineNs': str(time.monotonic_ns()+rule['timeoutMs']*1000000)}
            self.actions[key] = action;self._save('actions', identifier, action)
            if action['status'] == 'SENT' and not self.publish(rule['topic'], message, expiry=rule['expiryMs']-age):
                action['status'] = 'UNKNOWN';self._save('actions', identifier, action)
            self.event('ACTION_'+action['status'], action=action)

    def collect(self, state):
        directory = self.root/'records'
        if self.baseline is None:
            self.baseline = {p.name for p in directory.glob('*.json')};write_json(self.folder/'baseline.json', sorted(self.baseline))
        if self.last_total == state.get('total'):return
        for path in directory.glob('*.json'):
            if path.name in self.baseline or path.name in self.known:continue
            saved = json.loads(path.read_text());payload = saved['payload'];decision = saved['decision']
            identifier = payload['bootId']+':'+str(payload['sequence']);external = decision.get('external', {})
            message = {**decision, 'resultId': identifier, 'requestId': saved['requestId'], 'pieceId': external.get('pieceId', ''),
                       'productId': payload['planId'], 'productVersion': payload['planVersion'], 'modelVersion': payload['modelVersion'],
                       'consensus': payload.get('passage', {}).get('consensus'), 'evidence': path.name}
            result = {'resultId': identifier, 'file': path.name, 'acked': False, 'message': message}
            self.results[self.key(identifier)] = result;self._save('results', identifier, result);self.known.add(path.name)
            self.pending.add(self.key(identifier))
            self._outputs(message, payload)
        self.last_total = state.get('total')

    def step(self):
        for _ in range(16):
            try:topic, body, received = self.messages.get_nowait()
            except queue.Empty:break
            try:
                if topic == self.topics()['command']:self.command(body, received)
                else:self.receipt(topic, body)
            except Exception as exc:self._reply({'requestId': body.get('requestId') if isinstance(body, dict) else None, 'status': 'REJECTED', 'error': str(exc)})
        for document in list(self.commands.values()):
            if document['status'] != 'RUNNING':continue
            try:
                job = self.engine('/inspect?requestId='+document['requestId'])
                if job['status'] != 'RUNNING':
                    document.update(status=job['status'], job=job);self._save('commands', document['requestId'], document);self._reply(document)
            except Exception as exc:self.error = str(exc)
        state = self.engine();self.collect(state)
        outgoing = {'sessionId': self.session, 'ready': bool(state.get('fresh') and state.get('model') and state.get('product') and not state.get('error') and not state.get('paused')),
                    'busy': bool(state.get('production') or state.get('inspectionRequestId')), 'production': state.get('production'),
                    'model': state.get('model'), 'product': state.get('product'), 'counts': state.get('counts'), 'error': state.get('error')}
        text = json.dumps(outgoing, sort_keys=True)
        if text != self.last_state:
            self.publish(self.topics()['state'], outgoing, True);self.last_state = text
            if outgoing['error']:self.event('INSPECTION_ERROR', error=outgoing['error'])
        now = time.monotonic()
        published = 0
        for key in list(self.pending):
            result = self.results[key]
            if now >= self.due.get(result['resultId'], 0):
                self.publish(self.topics()['result'], result['message']);self.due[result['resultId']] = now+2
                published += 1
                if published >= 8:break
        for action in self.actions.values():
            if action['status'] in ('SENT', 'ACCEPTED') and time.monotonic_ns()>int(action['deadlineNs']):
                action.update(status='TIMEOUT');self._save('actions', action['actionId'], action);self.event('ACTION_TIMEOUT', action=action)

    def run(self):
        while self.running:
            try:
                if self.applied != self.revision or (self.config['enabled'] and not self.connected and time.monotonic()>=self.retry_at):self._connect()
                if self.config['enabled']:
                    with self.lock:self.step()
            except Exception as exc:self.error = str(exc);self.retry_at = time.monotonic()+5
            time.sleep(.1)
        if self.client:
            if self.connected:self.publish(self.topics()['availability'], {'online': False}, True)
            self.client.disconnect();self.client.loop_stop()
