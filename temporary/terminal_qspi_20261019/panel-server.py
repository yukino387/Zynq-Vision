from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

panel = Path(__file__).resolve().parents[2] / 'camera/terminal/build/arm/vision-panel'
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass
    def do_GET(self):
        if self.client_address[0] != '169.254.140.110' or self.path != '/panel':
            self.send_error(403)
            return
        self.send_response(200)
        self.send_header('Content-Length', str(panel.stat().st_size))
        self.end_headers()
        self.wfile.write(panel.read_bytes())
HTTPServer(('169.254.140.109', 9090), Handler).serve_forever()
