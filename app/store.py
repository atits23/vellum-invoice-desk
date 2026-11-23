import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

class ClosingConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()

def now():
    return datetime.now(timezone.utc).isoformat()

class Store:
    def __init__(self, directory, database_url=None, schema='vellum_engine'):
        self.database_url=database_url
        self.schema=schema
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / 'uploads').mkdir(exist_ok=True)
        self.path = self.root / 'invoices.sqlite3'
        with self.connect() as c:
            c.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS vendors(id TEXT PRIMARY KEY, name TEXT NOT NULL, tax_id TEXT NOT NULL, approved INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS purchase_orders(number TEXT PRIMARY KEY, vendor_id TEXT NOT NULL REFERENCES vendors(id), currency TEXT NOT NULL, amount_minor INTEGER NOT NULL, reserved_minor INTEGER NOT NULL DEFAULT 0, state TEXT NOT NULL DEFAULT 'OPEN');
            CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, filename TEXT NOT NULL, digest TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, fields TEXT NOT NULL DEFAULT '{}', evidence TEXT NOT NULL DEFAULT '{}', extracted_text TEXT NOT NULL DEFAULT '', conflicts TEXT NOT NULL DEFAULT '[]', ocr INTEGER NOT NULL DEFAULT 0, decision TEXT NOT NULL DEFAULT '{}', vendor_id TEXT, invoice_key TEXT, error TEXT);
            CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL REFERENCES runs(id), stage TEXT NOT NULL, message TEXT NOT NULL, at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS duplicate_lookup ON runs(vendor_id,invoice_key,status);
            CREATE TABLE IF NOT EXISTS migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS policy(id INTEGER PRIMARY KEY CHECK(id=1), tolerance_percent REAL NOT NULL DEFAULT 2, tolerance_absolute REAL NOT NULL DEFAULT 0);
            INSERT OR IGNORE INTO policy(id) VALUES(1);
            CREATE TABLE IF NOT EXISTS po_items(po_number TEXT NOT NULL REFERENCES purchase_orders(number), description TEXT NOT NULL, quantity TEXT NOT NULL, unit_price TEXT NOT NULL, unit TEXT NOT NULL DEFAULT 'each');
            CREATE TABLE IF NOT EXISTS admin_audit(id INTEGER PRIMARY KEY AUTOINCREMENT,actor TEXT,action TEXT,payload TEXT,at TEXT);
            ''')
            if self.database_url:c.execute('CREATE TABLE IF NOT EXISTS uploaded_sources(run_id TEXT PRIMARY KEY,body BYTEA NOT NULL)')
            for table,column,definition in [('runs','metadata',"TEXT NOT NULL DEFAULT '{}'"),('purchase_orders','expires','TEXT'),('events','detail',"TEXT NOT NULL DEFAULT '{}'"),('runs','attempts','INTEGER NOT NULL DEFAULT 0')]:
                if column not in [r[1] for r in c.execute('PRAGMA table_info('+table+')')]:c.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
            c.execute('INSERT OR IGNORE INTO migrations VALUES(2,?)',(now(),))
            if not c.execute('SELECT 1 FROM vendors LIMIT 1').fetchone():
                c.executemany('INSERT INTO vendors VALUES(?,?,?,?)', [('v1','Acme Cloud Services','ACME-TAX-001',1),('v2','Northstar Design Studio','NORTH-TAX-002',1),('v3','Blocked Supplies Ltd','BLOCK-TAX-003',0)])
                c.executemany('INSERT INTO purchase_orders(number,vendor_id,currency,amount_minor,state) VALUES(?,?,?,?,?)', [('PO-1001','v1','USD',100000,'OPEN'),('PO-2001','v2','USD',200000,'OPEN'),('PO-2002','v2','USD',200000,'OPEN'),('PO-3001','v3','USD',100000,'OPEN'),('PO-CLOSED','v1','USD',100000,'CLOSED')])
            if not c.execute('SELECT 1 FROM po_items LIMIT 1').fetchone():
                c.executemany('INSERT INTO po_items VALUES(?,?,?,?,?)',[('PO-1001','Cloud subscription','10','100.00','each'),('PO-2001','Design services','20','100.00','hour'),('PO-2002','Laptop','2','1000.00','each')])

    def connect(self):
        if self.database_url:
            from app.postgres import Connection
            return Connection(self.database_url,self.schema)
        c = sqlite3.connect(self.path, timeout=30, factory=ClosingConnection)
        c.row_factory = sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON')
        return c

    def source(self,run_id):
        if self.database_url:
            with self.connect() as c:
                row=c.execute('SELECT body FROM uploaded_sources WHERE run_id=?',(run_id,)).fetchone()
                if row:return bytes(row['body'])
            raise ValueError('Original source unavailable.')
        return (self.root/'uploads'/(run_id+'.pdf')).read_bytes()

    def materialize(self,run_id):
        path=self.root/'uploads'/(run_id+'.pdf')
        if self.database_url and not path.exists():path.write_bytes(self.source(run_id))
        return path

    def event(self, run_id, stage, message, conn=None, detail=None):
        if conn is not None:
            conn.execute('INSERT INTO events(run_id,stage,message,at,detail) VALUES(?,?,?,?,?)', (run_id,stage,message,now(),json.dumps(detail or {})))
        else:
            with self.connect() as c:
                self.event(run_id,stage,message,c,detail)

    def get(self, run_id):
        with self.connect() as c:
            row = c.execute('SELECT * FROM runs WHERE id=?', (run_id,)).fetchone()
            if not row:
                return None
            result = dict(row)
            for key in ['fields','evidence','conflicts','decision','metadata']:
                result[key] = json.loads(result[key])
            result['events'] = [dict(e) for e in c.execute('SELECT * FROM events WHERE run_id=? ORDER BY id', (run_id,))]
            for event in result['events']:event['detail']=json.loads(event['detail'])
            return result

    def list(self):
        with self.connect() as c:
            return [dict(r) for r in c.execute('SELECT id,filename,status,created_at,updated_at,fields,decision FROM runs ORDER BY created_at DESC LIMIT 500')]
