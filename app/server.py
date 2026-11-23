import csv
import hmac
import io
import json
import os
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, unquote
from app.store import Store
from app.service import Service, MAX_BYTES

ROOT = Path(__file__).resolve().parent.parent

def make_server(host='127.0.0.1', port=8000, data_dir=None):
    store = Store(data_dir or os.environ.get('DATA_DIR', str(ROOT/'data')),os.environ.get('DATABASE_URL'),os.environ.get('ENGINE_DB_SCHEMA','vellum_engine'))
    service = Service(store)
    token = os.environ.get('APP_TOKEN','')
    if os.environ.get('APP_ENV') == 'production' and len(token) < 24:
        raise ValueError('Production requires APP_TOKEN with at least 24 characters.')

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Do not log request URLs or credentials.
            pass

        def send(self, value, status=200, content_type='application/json', attachment=None):
            body = json.dumps(value).encode() if content_type == 'application/json' else value
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
            if attachment:
                self.send_header('Content-Disposition',f'attachment; filename="{attachment}"')
            self.end_headers()
            self.wfile.write(body)

        def authorized(self):
            if token and not hmac.compare_digest(self.headers.get('Authorization',''), 'Bearer '+token):
                self.send({'error':'Enter the workspace access token.'},401)
                return False
            return True

        def do_GET(self):
            path = urlparse(self.path).path
            if path == '/health':
                return self.send({'status':'ok'})
            if path.startswith('/api/'):
                if not self.authorized():
                    return
                if path == '/api/runs':
                    return self.send(store.list())
                if path == '/api/procurement':
                    with store.connect() as c:
                        return self.send({'policy':dict(c.execute('SELECT * FROM policy WHERE id=1').fetchone()),'vendors':[dict(r) for r in c.execute('SELECT * FROM vendors')], 'pos':[dict(r) for r in c.execute('SELECT p.*,v.name AS vendor FROM purchase_orders p JOIN vendors v ON v.id=p.vendor_id')]})
                if path == '/api/policy':
                    with store.connect() as c:return self.send(dict(c.execute('SELECT * FROM policy WHERE id=1').fetchone()))
                if path == '/api/samples':
                    return self.send([p.name for p in sorted((ROOT/'samples').glob('*.pdf'))])
                if path.startswith('/api/samples/'):
                    name = unquote(path.removeprefix('/api/samples/'))
                    if name not in [p.name for p in (ROOT/'samples').glob('*.pdf')]:
                        return self.send({'error':'Not found'},404)
                    return self.send((ROOT/'samples'/name).read_bytes(),content_type='application/pdf',attachment=name)
                if path == '/api/export.csv':
                    output = io.StringIO()
                    writer = csv.writer(output)
                    writer.writerow(['Run','File','Status','Vendor','Invoice','Currency','Total','Created'])
                    for r in store.list():
                        f = json.loads(r['fields'])
                        values = [r['id'],r['filename'],r['status'],f.get('vendor',''),f.get('invoice_number',''),f.get('currency',''),f.get('total',''),r['created_at']]
                        writer.writerow(["'"+str(v) if str(v).startswith(('=','+','-','@','\t','\r')) else v for v in values])
                    return self.send(output.getvalue().encode(),content_type='text/csv; charset=utf-8',attachment='invoice-history.csv')
                match = re.fullmatch(r'/api/runs/([a-f0-9]{32})(/source|/export)?',path)
                if match:
                    run = store.get(match[1])
                    if not run:
                        return self.send({'error':'Run not found'},404)
                    if match[2] == '/source':
                        body=store.source(match[1])
                        kind='application/pdf' if body.startswith(b'%PDF') else 'image/png' if body.startswith(b'\x89PNG') else 'image/jpeg'
                        return self.send(body,content_type=kind)
                    if match[2] == '/export':
                        return self.send(json.dumps(run,indent=2).encode(),content_type='application/octet-stream',attachment='decision-'+match[1][:8]+'.json')
                    return self.send(run)
                return self.send({'error':'Not found'},404)
            assets = {'/':'index.html','/app.js':'app.js','/style.css':'style.css'}
            if path not in assets:
                return self.send({'error':'Not found'},404)
            types = {'/':'text/html; charset=utf-8','/app.js':'text/javascript; charset=utf-8','/style.css':'text/css; charset=utf-8'}
            return self.send((ROOT/'static'/assets[path]).read_bytes(),content_type=types[path])

        def do_POST(self):
            if not self.authorized():
                return
            # No cookies/CORS: browser requests require bearer auth and same-origin JSON/raw PDF.
            path = urlparse(self.path).path
            try:
                length = int(self.headers.get('Content-Length','0'))
                if length <= 0 or length > MAX_BYTES:
                    return self.send({'error':'Request must contain 1 byte to 10 MB.'},413)
                self.connection.settimeout(30)
                body = self.rfile.read(length)
                if len(body) != length:
                    raise ValueError('Incomplete upload.')
                if path == '/api/runs':
                    run_id = service.submit(body,unquote(self.headers.get('X-Filename','invoice.pdf')))
                    return self.send({'id':run_id},202)
                if path in ['/api/policy','/api/vendors']:
                    data=json.loads(body)
                    with store.connect() as c:
                        if path=='/api/policy':
                            percent=float(data['tolerance_percent']);absolute=float(data['tolerance_absolute'])
                            if not 0<=percent<=10 or not 0<=absolute<=1000:raise ValueError('Tolerance outside supported bounds.')
                            c.execute('UPDATE policy SET tolerance_percent=?,tolerance_absolute=? WHERE id=1',(percent,absolute))
                        else:c.execute('UPDATE vendors SET approved=? WHERE id=?',(int(data['approved'] is True),data['id']))
                        c.execute('INSERT INTO admin_audit(actor,action,payload,at) VALUES(?,?,?,?)',(self.headers.get('X-Actor','admin'),path,json.dumps(data),__import__('app.store',fromlist=['now']).now()))
                    return self.send({'message':'Settings saved. Future decisions use the updated policy.'})
                match = re.fullmatch(r'/api/runs/([a-f0-9]{32})/(review|reject|override)',path)
                if match:
                    data = json.loads(body)
                    note = data.get('note','')
                    if not isinstance(note,str) or not 5 <= len(note.strip()) <= 2000:
                        raise ValueError('Enter a review note between 5 and 2000 characters.')
                    if match[2] == 'override':
                        return self.send(service.override(match[1],data.get('status'),note,self.headers.get('X-Actor','Administrator')))
                    if match[2] == 'reject':
                        service.reject(match[1],note,self.headers.get('X-Actor','AP reviewer'))
                        return self.send(store.get(match[1]))
                    fields = data.get('fields')
                    allowed = {'vendor','tax_id','invoice_number','invoice_date','due_date','po_number','currency','subtotal','tax','total','items','cgst','sgst','igst','discount','shipping','round_off','document_type'}
                    if not isinstance(fields,dict) or set(fields)-allowed or any(not isinstance(v,str) or len(v)>500 for k,v in fields.items() if k != 'items'):
                        raise ValueError('Invalid field values.')
                    original = store.get(match[1])
                    if not original:
                        return self.send({'error':'Run not found'},404)
                    # Preserve original line items: structured edits cannot bypass line checks.
                    fields['items'] = original['fields'].get('items',[])
                    return self.send(service.decide(match[1],fields,note,data.get('verified') is True,self.headers.get('X-Actor','AP reviewer')))
                return self.send({'error':'Not found'},404)
            except (ValueError,TypeError,KeyError) as exc:
                return self.send({'error':str(exc)},400)
            except Exception:
                return self.send({'error':'Request failed. Please retry or inspect the saved run.'},500)

    server = ThreadingHTTPServer((host,port),Handler)
    server.service = service
    return server

if __name__ == '__main__':
    server = make_server(os.environ.get('HOST','127.0.0.1'),int(os.environ.get('PORT','8000')))
    print(f'Invoice Desk listening on http://{server.server_address[0]}:{server.server_address[1]}',flush=True)
    server.serve_forever()
