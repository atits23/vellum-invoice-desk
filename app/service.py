import hashlib
import io
import json
import queue
import shutil
import subprocess
import tempfile
import threading
import uuid
import sys
import time
from pathlib import Path
from pypdf import PdfReader
from app.engine import evaluate
from app.store import now

MAX_BYTES = 10 * 1024 * 1024
MAX_PAGES = 15

def read_pdf(path):
    reader = PdfReader(path)
    if reader.is_encrypted:
        raise ValueError('Password-protected PDFs are not supported. Upload a decrypted copy.')
    if not 1 <= len(reader.pages) <= MAX_PAGES:
        raise ValueError(f'Upload a PDF with 1–{MAX_PAGES} pages.')
    parts, used_ocr = [], False
    for index, page in enumerate(reader.pages):
        text = page.extract_text() or ''
        # Image-bearing pages are OCRed as a whole to avoid overlooking scanned totals.
        has_images = bool(page.images)
        if len(text.strip()) < 40 or has_images:
            if not shutil.which('pdftoppm') or not shutil.which('tesseract'):
                raise ValueError('This document needs OCR. Install Tesseract and Poppler, or use the Docker deployment with OCR included.')
            with tempfile.TemporaryDirectory() as temporary:
                prefix = str(Path(temporary) / 'page')
                subprocess.run(['pdftoppm','-f',str(index+1),'-l',str(index+1),'-singlefile','-scale-to','2200','-png',str(path),prefix], check=True, capture_output=True, timeout=45)
                process = subprocess.run(['tesseract',prefix+'.png','stdout','--psm','6'], check=True, capture_output=True, timeout=45)
                text = process.stdout.decode('utf-8', errors='replace')
            used_ocr = True
        parts.append(text)
    text = '\n'.join(parts)
    if not text.strip():
        raise ValueError('No readable content found. Upload a clearer scan.')
    if len(text) > 250000:
        raise ValueError('Extracted document is too large.')
    return text, used_ocr

class Service:
    def __init__(self, store, start_worker=True):
        self.store = store
        self.queue = queue.Queue(maxsize=100)
        if start_worker:
            with store.connect() as c:
                c.execute("UPDATE runs SET status='QUEUED' WHERE status='PROCESSING'")
                pending = [r['id'] for r in c.execute("SELECT id FROM runs WHERE status='QUEUED' ORDER BY created_at")]
            threading.Thread(target=self.worker, daemon=True).start()
            for run_id in pending:
                self.queue.put(run_id)

    def submit(self, body, filename):
        if not body or len(body) > MAX_BYTES:
            raise ValueError('Upload a PDF up to 10 MB.')
        if not (body.startswith(b'%PDF-') or body.startswith(b'\x89PNG\r\n\x1a\n') or body.startswith(b'\xff\xd8\xff')):
            raise ValueError('Unsupported input. Upload a PDF, PNG or JPEG.')
        if self.queue.full():
            raise ValueError('Processing queue is full. Please try again shortly.')
        run_id = uuid.uuid4().hex
        path = self.store.root / 'uploads' / (run_id + '.pdf')
        if not self.store.database_url:path.write_bytes(body)
        with self.store.connect() as c:
            if self.store.database_url:
                c.execute('BEGIN IMMEDIATE')
                size=c.execute('SELECT COALESCE(SUM(OCTET_LENGTH(body)),0) AS bytes FROM uploaded_sources').fetchone()['bytes']
                if size+len(body)>200*1024*1024:raise ValueError('Demo storage quota reached (200 MB). Ask an administrator to archive old documents.')
                c.execute('INSERT INTO uploaded_sources VALUES(?,?)',(run_id,body))
            c.execute('INSERT INTO runs(id,filename,digest,status,created_at,updated_at) VALUES(?,?,?,?,?,?)', (run_id,Path(filename.replace('\\','/')).name[:180],hashlib.sha256(body).hexdigest(),'QUEUED',now(),now()))
            self.store.event(run_id,'received',f'Received {len(body):,} bytes; original source preserved.',c,{'status':'completed','started_at':now(),'ended_at':now(),'duration_ms':0,'inputs':{'bytes':len(body)},'outputs':{'sha256':hashlib.sha256(body).hexdigest()},'confidence':None})
        self.queue.put(run_id)
        return run_id

    def worker(self):
        while True:
            run_id = self.queue.get()
            try:
                if run_id is None:
                    return
                self.process(run_id)
            finally:
                self.queue.task_done()

    def stop(self):
        self.queue.put(None)
        self.queue.join()

    def process(self, run_id):
        from app.engine import extract
        try:
            started=now();timer=time.perf_counter()
            with self.store.connect() as c:
                if c.execute('SELECT status FROM runs WHERE id=?',(run_id,)).fetchone()['status'] not in ('QUEUED','PROCESSING'):return
                c.execute("UPDATE runs SET status='PROCESSING',updated_at=?,attempts=attempts+1 WHERE id=?", (now(),run_id))
            self.store.event(run_id,'extracted','Reading PDF/image; isolated parser with a 120-second timeout.',detail={'status':'running','started_at':started,'inputs':{'source':run_id}})
            with tempfile.TemporaryDirectory() as temp:
                output=Path(temp)/'extracted.json'
                process=subprocess.run([sys.executable,'-m','app.documents',str(self.store.materialize(run_id)),str(output)],capture_output=True,timeout=120)
                if process.returncode or not output.exists():raise ValueError('Document parser failed; upload a valid readable document.')
                parsed=json.loads(output.read_text(encoding='utf-8'))
            if parsed.get('error'):raise ValueError(parsed['error'])
            text,metadata=parsed['text'],parsed['metadata'];ocr=metadata['ocr_confidence'] is not None
            fields, evidence, conflicts = extract(text)
            with self.store.connect() as c:
                c.execute('UPDATE runs SET fields=?,evidence=?,extracted_text=?,conflicts=?,ocr=?,metadata=? WHERE id=?', (json.dumps(fields),json.dumps(evidence),text,json.dumps(conflicts),int(ocr),json.dumps(metadata),run_id))
            self.store.event(run_id,'extracted',f'Extracted {len(evidence)} fields using '+metadata['method']+'.',detail={'status':'completed','started_at':started,'ended_at':now(),'duration_ms':round((time.perf_counter()-timer)*1000,2),'inputs':{'pages':metadata['pages']},'outputs':fields,'confidence':metadata['ocr_confidence']})
            self.decide(run_id)
        except Exception as exc:
            if isinstance(exc,(subprocess.TimeoutExpired,subprocess.CalledProcessError)):
                with self.store.connect() as c:
                    attempts=c.execute('SELECT attempts FROM runs WHERE id=?',(run_id,)).fetchone()['attempts']
                    if attempts<2:
                        c.execute("UPDATE runs SET status='QUEUED' WHERE id=?",(run_id,))
                        self.store.event(run_id,'retry','Transient parser failure; retrying once with the same run identity.',c)
                if attempts<2:return self.process(run_id)
            message = str(exc) if isinstance(exc, ValueError) else 'PDF processing failed. The document may be malformed or OCR timed out; upload a readable PDF.'
            with self.store.connect() as c:
                status='REVIEW' if ('OCR' in message or isinstance(exc,subprocess.TimeoutExpired)) else 'REJECTED'
                decision={'status':status,'rules':[{'code':'readable_document','passed':False,'message':message}],'next_action':message,'policy_version':'2026.2'}
                c.execute('UPDATE runs SET status=?,error=?,decision=?,updated_at=? WHERE id=?', (status,message,json.dumps(decision),now(),run_id))
                self.store.event(run_id,'decision',message,c,{'status':'failed','started_at':started,'ended_at':now(),'duration_ms':round((time.perf_counter()-timer)*1000,2),'outputs':decision,'confidence':0})

    def decide(self, run_id, corrected=None, note='', verified=False,actor='AP reviewer'):
        with self.store.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT * FROM runs WHERE id=?', (run_id,)).fetchone()
            if not row:
                raise ValueError('Run not found.')
            if corrected is not None and row['status'] != 'REVIEW':
                raise ValueError('Only runs awaiting review can be corrected.')
            if corrected is None and row['status'] != 'PROCESSING':
                raise ValueError('Run is not processing.')
            fields = corrected if corrected is not None else json.loads(row['fields'])
            start=now();timer=time.perf_counter()
            decision = evaluate(c,run_id,fields,row['digest'],bool(row['ocr']),json.loads(row['conflicts']),verified)
            if corrected is not None:
                self.store.event(run_id,'review',json.dumps({'actor':actor,'note':note,'before':json.loads(row['fields']),'after':fields,'source_verified':verified}),c)
            detail={'status':'completed','started_at':start,'ended_at':now(),'duration_ms':round((time.perf_counter()-timer)*1000,2),'confidence':None,'inputs':{'policy_version':'2026.2'}}
            self.store.event(run_id,'validated','Validated fields, identity, dates and arithmetic.',c,{**detail,'outputs':decision['rules']})
            self.store.event(run_id,'po_matched','Explicit or uniquely inferred PO; uncertainty is never guessed.',c,{**detail,'outputs':decision['po']})
            self.store.event(run_id,'rules_checked','Checked duplicate, vendor, item and cumulative budget controls.',c,{**detail,'outputs':decision['rules']})
            if decision['status'] == 'APPROVED':
                c.execute('UPDATE purchase_orders SET reserved_minor=reserved_minor+? WHERE number=?', (decision['total_minor'],decision['po']['number']))
            c.execute('UPDATE runs SET status=?,fields=?,decision=?,vendor_id=?,invoice_key=?,updated_at=? WHERE id=?', (decision['status'],json.dumps(fields),json.dumps(decision),decision['vendor_id'],decision['invoice_key'],now(),run_id))
            self.store.event(run_id,'decision',decision['status'] + ': ' + decision['next_action'],c,{**detail,'outputs':decision['status']})
        return self.store.get(run_id)

    def override(self,run_id,status,note,actor):
        if not isinstance(note,str) or not 5<=len(note.strip())<=2000:raise ValueError('An audit note of 5 to 2000 characters is required.')
        if status not in ('APPROVED','REVIEW','REJECTED'):raise ValueError('Invalid override decision.')
        with self.store.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row=c.execute('SELECT * FROM runs WHERE id=?',(run_id,)).fetchone()
            if not row or row['status'] in ('QUEUED','PROCESSING'):raise ValueError('Wait for processing to finish before overriding.')
            original=json.loads(row['decision']);po=original.get('po');amount=original.get('total_minor')
            if status=='APPROVED' and (not po or not amount or amount<=0):raise ValueError('An approval requires a matched PO and a valid positive amount. Correct and revalidate the invoice first.')
            if row['status']=='APPROVED' and po and amount:c.execute('UPDATE purchase_orders SET reserved_minor=reserved_minor-? WHERE number=?',(amount,po['number']))
            if status=='APPROVED':c.execute('UPDATE purchase_orders SET reserved_minor=reserved_minor+? WHERE number=?',(amount,po['number']))
            decision={**original,'status':status,'manual_override':True,'automated_status':original.get('automated_status',row['status']),'next_action':'Administrator override: '+note}
            c.execute('UPDATE runs SET status=?,decision=?,updated_at=? WHERE id=?',(status,json.dumps(decision),now(),run_id))
            self.store.event(run_id,'override','Explicit administrator override; this is not an automated approval.',c,{'actor':actor,'note':note,'before':{'status':row['status'],'decision':original},'after':{'status':status,'decision':decision}})
        return self.store.get(run_id)

    def reject(self, run_id, note,actor='AP reviewer'):
        with self.store.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            row = c.execute('SELECT status FROM runs WHERE id=?',(run_id,)).fetchone()
            if not row or row['status'] != 'REVIEW':
                raise ValueError('Only runs awaiting review can be rejected.')
            c.execute("UPDATE runs SET status='REJECTED',updated_at=? WHERE id=?",(now(),run_id))
            self.store.event(run_id,'rejected',actor+': '+note,c,{'actor':actor,'note':note,'before':{'status':row['status']},'after':{'status':'REJECTED'}})
