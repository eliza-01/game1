from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import json, os, sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from character_store import CharacterStore
CONTROL_AGENT_BUILD="game1-m1-002"
ROOT=Path(__file__).resolve().parents[2]
PORT=int(os.environ.get('CONTROL_AGENT_PORT','43821'))
TOKEN=os.environ.get('CONTROL_TOKEN','Game1LocalControlV1')
STORE=CharacterStore(ROOT)
class H(BaseHTTPRequestHandler):
    def out(self,status,obj):
        b=json.dumps(obj,ensure_ascii=False).encode(); self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
    def auth(self): return self.headers.get('X-Control-Token')==TOKEN
    def body(self):
        n=int(self.headers.get('Content-Length','0')); return json.loads(self.rfile.read(n) or b'{}')
    def do_GET(self):
        if not self.auth(): return self.out(401,{'error':'unauthorized'})
        if self.path=='/api/agent/info': return self.out(200,{'build':CONTROL_AGENT_BUILD,'project':'game1','projectRoot':str(ROOT),'db':str(STORE.db)})
        if self.path=='/api/characters': return self.out(200,{'items':STORE.list()})
        return self.out(404,{'error':'not found'})
    def do_POST(self):
        if not self.auth(): return self.out(401,{'error':'unauthorized'})
        if self.path=='/api/characters':
            try:return self.out(200,STORE.put(self.body()))
            except Exception as e:return self.out(400,{'error':str(e)})
        return self.out(404,{'error':'not found'})
    def do_DELETE(self):
        if not self.auth(): return self.out(401,{'error':'unauthorized'})
        prefix='/api/characters/'
        if self.path.startswith(prefix): STORE.delete(self.path[len(prefix):]); return self.out(200,{'ok':True})
        return self.out(404,{'error':'not found'})
    def log_message(self,fmt,*args): print('[host-agent]',fmt%args)
if __name__=='__main__':
    print(f'[game1] control agent http://127.0.0.1:{PORT} · {ROOT}')
    ThreadingHTTPServer(('127.0.0.1',PORT),H).serve_forever()
