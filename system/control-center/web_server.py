from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from pathlib import Path
import json, os
AGENT=os.environ.get('CONTROL_AGENT_URL','http://host.docker.internal:43821')
TOKEN=os.environ.get('CONTROL_TOKEN','Game1LocalControlV1')
STATIC=Path(__file__).resolve().parent/'static'
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/api/'): return self.proxy()
        p=STATIC/('index.html' if self.path=='/' else self.path.lstrip('/'))
        if not p.is_file(): self.send_error(404); return
        b=p.read_bytes(); self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8' if p.suffix=='.html' else 'text/plain'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_POST(self): self.proxy()
    def do_DELETE(self): self.proxy()
    def proxy(self):
        body=self.rfile.read(int(self.headers.get('Content-Length','0'))) if self.command in ('POST','PUT','PATCH') else None
        req=Request(AGENT+self.path,data=body,method=self.command,headers={'X-Control-Token':TOKEN,'Content-Type':'application/json'})
        try:
            with urlopen(req,timeout=10) as r: data=r.read(); status=r.status
        except HTTPError as e: data=e.read(); status=e.code
        except Exception as e: data=json.dumps({'error':str(e)}).encode(); status=502
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
if __name__=='__main__': ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('WEB_PORT','8080'))),H).serve_forever()
