"""Platform administrator login; credentials and bearer tokens never persist locally."""
import hashlib
import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


class AuthError(Exception):
    def __init__(self, message, status=403):
        super().__init__(message)
        self.status = status


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Authority:
    session_seconds = 1800

    def __init__(self, connection):
        self.connection = connection
        self.lock = threading.RLock()
        self.sessions = {}
        self.http = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    @staticmethod
    def valid_server(server):
        if not isinstance(server, str):
            raise ValueError('平台地址无效')
        server = server.rstrip('/')
        parsed = urllib.parse.urlsplit(server)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path:
            raise ValueError('请输入完整平台地址，如 http://192.168.1.10:3000')
        return server

    def _server(self):
        try:
            server = self.valid_server(json.loads(self.connection.read_text())['server'])
            return server
        except (OSError, ValueError, KeyError, TypeError):
            raise AuthError('尚未连接平台；管理员可填写平台地址登录', 409)

    def _remote(self, server, path, document=None, bearer=''):
        request = urllib.request.Request(server+path,
            None if document is None else json.dumps(document).encode(),
            {'Content-Type': 'application/json', 'Authorization': 'Bearer '+bearer})
        try:
            with self.http.open(request, timeout=2) as reply:
                return json.loads(reply.read(65536))
        except urllib.error.HTTPError as exc:
            if exc.code >= 500:
                raise AuthError('平台暂不可用；现有作业仍可检测', 503) from None
            if exc.code == 401:
                raise AuthError('账号或密码错误，或平台登录已失效', 401) from None
            if exc.code == 429:
                raise AuthError('尝试次数过多，请稍后重试', 429) from None
            raise AuthError('平台拒绝登录或权限校验，请联系管理员', 403) from None
        except (OSError, ValueError):
            raise AuthError('无法连接平台；现有作业仍可检测，管理操作需联网', 503) from None

    def _key(self, token):
        return hashlib.sha256(token.encode()).digest()

    def status(self, token=''):
        with self.lock:
            now = time.monotonic()
            self.sessions = {key: item for key, item in self.sessions.items() if item['until'] > now}
            result = {'role': 'operator', 'username': '操作员', 'remainingSeconds': 0, 'message': ''}
            session = self.sessions.get(self._key(token))
            try:
                server = self._server() if self.connection.exists() else session['server'] if session else self._server()
                result['configured'] = True
                result['server'] = server
            except AuthError as exc:
                result.update(configured=False, server='', message=str(exc))
                return result
            session = self.sessions.get(self._key(token))
            if not session:
                return result
            try:
                if session['server'] != server:
                    raise AuthError('平台连接已变化，请重新登录', 401)
                user = self._remote(server, '/api/auth/me', bearer=session['bearer'])
                if user.get('role') != 'ADMIN':
                    raise AuthError('此账号没有平台管理员权限', 403)
                result.update(role='admin', username=user['name'], remainingSeconds=max(0, int(session['until']-now)))
            except AuthError as exc:
                result['message'] = str(exc)
                if exc.status != 503:
                    self.sessions.pop(self._key(token), None)
            return result

    def require(self, token):
        status = self.status(token)
        if status['role'] != 'admin':
            raise AuthError(status['message'] or '请使用平台管理员账号登录')

    def request(self, path, document, token=''):
        with self.lock:
            if path == '/auth/logout':
                self.sessions.pop(self._key(token), None)
                return self.status()
            if path != '/auth/login':
                raise AuthError('请在平台账户设置中维护账号和密码', 404)
            username, password = document.get('username'), document.get('password')
            if not isinstance(username, str) or not 1 <= len(username) <= 80 or not isinstance(password, str) or not 1 <= len(password) <= 200:
                raise AuthError('请输入平台账号和密码', 400)
            requested = document.get('server')
            if not isinstance(requested, str) or not requested:
                requested = self._server() if self.connection.exists() else ''
            server = self.valid_server(requested)
            reply = self._remote(server, '/api/auth/login', {'username': username, 'password': password})
            bearer = reply.get('token')
            if not isinstance(bearer, str) or not bearer:
                raise AuthError('平台登录响应无效', 503)
            user = self._remote(server, '/api/auth/me', bearer=bearer)
            if user.get('role') != 'ADMIN':
                raise AuthError('此账号没有平台管理员权限', 403)
            self.sessions.clear()
            local = secrets.token_urlsafe(32)
            self.sessions[self._key(local)] = {'server': server, 'bearer': bearer, 'until': time.monotonic()+self.session_seconds}
            return dict(self.status(local), token=local)

    def platform_device(self, token, server, device_id):
        with self.lock:
            self.require(token)
            session = self.sessions[self._key(token)]
            if self.valid_server(server) != session['server']:
                raise AuthError('连接配置的平台地址与当前登录平台不一致')
            device = self._remote(server, '/api/devices/'+urllib.parse.quote(device_id, safe=''), bearer=session['bearer'])
            if device.get('id') != device_id or device.get('type') != 'ZYNQ':
                raise AuthError('此平台不存在对应的 Zynq 终端')

    def platform_request(self, token, path, document=None, binary=False):
        with self.lock:
            self.require(token)
            session = self.sessions[self._key(token)]
            if not binary:
                return self._remote(session['server'], path, document, session['bearer'])
            request = urllib.request.Request(session['server']+path, headers={'Authorization': 'Bearer '+session['bearer']})
            try:
                with self.http.open(request, timeout=15) as reply:
                    data = reply.read(16*1024*1024+1)
                if len(data) > 16*1024*1024:
                    raise AuthError('平台作业包超出大小限制', 422)
                return data
            except urllib.error.HTTPError as exc:
                raise AuthError('平台作业包不可用，请刷新作业列表', exc.code) from None
            except OSError:
                raise AuthError('平台作业包下载失败，请检查连接后重试', 503) from None
