"""Test server for the Worker tests (see docs/website.md): serves harness.html and the Worker file, the data files the tests
upload, and passes /stkapi/* on to the local toolkit (same origin, like the tunnel would)."""
import http.server, sys, urllib.request, urllib.error
from pathlib import Path
HERE = Path(__file__).parent
WORKER = Path(sys.argv[1]); DATA = Path(sys.argv[2]); API = sys.argv[3]; PORT = int(sys.argv[4])
class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, code, body, ctype, extra=()):
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for k, v in extra: self.send_header(k, v)
        self.end_headers(); self.wfile.write(body)
    def _proxy(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else None
        req = urllib.request.Request(API + self.path[len("/stkapi"):], data=body, method=self.command)
        for k in ("Content-Type", "X-STK-Key"):
            if self.headers.get(k): req.add_header(k, self.headers[k])
        try:
            r = urllib.request.urlopen(req, timeout=120); code = r.status
        except urllib.error.HTTPError as e:
            r = e; code = e.code
        data = r.read()
        extra = [(k, r.headers[k]) for k in ("Content-Disposition", "X-Warning") if r.headers.get(k)]
        self._send(code, data, r.headers.get("Content-Type", "application/octet-stream"), extra)
    def do_GET(self):
        if self.path.startswith("/stkapi/"): return self._proxy()
        if self.path == "/": return self._send(200, (HERE / "harness.html").read_bytes(), "text/html")
        if self.path == "/worker.js": return self._send(200, WORKER.read_bytes(), "text/javascript")
        if self.path.startswith("/data/"):
            f = DATA / urllib.request.unquote(self.path[6:])
            return self._send(200, f.read_bytes(), "application/octet-stream")
        self._send(404, b"no", "text/plain")
    def do_POST(self):
        if self.path.startswith("/stkapi/"): return self._proxy()
        self._send(404, b"no", "text/plain")
http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
