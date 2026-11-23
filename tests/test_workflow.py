import io
import json
import tempfile
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from app.engine import extract, money
from app.store import Store, now
from app.service import Service, read_pdf

ROOT=Path(__file__).resolve().parent.parent
BASE=dict(vendor='Acme Cloud Services',tax_id='ACME-TAX-001',invoice_number='INV-1',invoice_date='2026-10-15',due_date='2026-11-15',po_number='PO-1001',currency='USD',subtotal='500.00',tax='100.00',total='600.00',items=[])

class Workflow(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(self.temp.name)
        self.service=Service(self.store,start_worker=False)
    def tearDown(self):
        self.temp.cleanup()
    def run_fields(self, changes=None, ocr=False, conflicts=None):
        rid=uuid.uuid4().hex
        fields={**BASE,**(changes or {})}
        with self.store.connect() as c:
            c.execute('INSERT INTO runs(id,filename,digest,status,created_at,updated_at,fields,ocr,conflicts) VALUES(?,?,?,?,?,?,?,?,?)',(rid,'test.pdf',rid,'PROCESSING',now(),now(),json.dumps(fields),int(ocr),json.dumps(conflicts or [])))
        return self.service.decide(rid)
    def failures(self, run):
        return {r['code'] for r in run['decision']['rules'] if not r['passed']}
    def test_happy_path_reserves(self):
        r=self.run_fields();self.assertEqual(r['status'],'APPROVED')
        with self.store.connect() as c:self.assertEqual(c.execute("SELECT reserved_minor FROM purchase_orders WHERE number='PO-1001'").fetchone()[0],60000)
    def test_split_exceeds_cumulative_budget(self):
        self.run_fields();r=self.run_fields(dict(invoice_number='INV-2',subtotal='400',tax='80',total='480'))
        self.assertIn('budget',self.failures(r))
    def test_tolerance_boundary(self):
        r=self.run_fields(dict(subtotal='1000',tax='20',total='1020'));self.assertEqual(r['status'],'APPROVED')
    def test_tolerance_exceeded(self):
        r=self.run_fields(dict(subtotal='1000',tax='20.01',total='1020.01'));self.assertIn('budget',self.failures(r))
    def test_semantic_duplicate(self):
        self.run_fields();r=self.run_fields(dict(invoice_number='inv/1'));self.assertIn('duplicate',self.failures(r))
    def test_ambiguous_po(self):
        r=self.run_fields(dict(vendor='Northstar Design Studio',tax_id='NORTH-TAX-002',po_number=''));self.assertIn('po_match',self.failures(r))
    def test_unique_inference(self):
        r=self.run_fields(dict(po_number=''));self.assertEqual(r['status'],'APPROVED');self.assertEqual(r['decision']['po']['number'],'PO-1001')
    def test_unknown_explicit_not_substituted(self):
        self.assertIn('po_match',self.failures(self.run_fields(dict(po_number='PO-WRONG'))))
    def test_wrong_vendor_po(self):
        self.assertIn('po_vendor',self.failures(self.run_fields(dict(po_number='PO-2001'))))
    def test_closed_po(self):
        self.assertIn('po_open',self.failures(self.run_fields(dict(po_number='PO-CLOSED'))))
    def test_currency_mismatch(self):
        self.assertIn('po_currency',self.failures(self.run_fields(dict(currency='EUR'))))
    def test_unsupported_currency(self):
        self.assertIn('currency',self.failures(self.run_fields(dict(currency='JPY'))))
    def test_unknown_vendor(self):
        self.assertIn('vendor_name_variant',self.failures(self.run_fields(dict(vendor='Acme Cloud Service'))))
    def test_tax_identity(self):
        self.assertIn('tax_identity',self.failures(self.run_fields(dict(tax_id='wrong'))))
    def test_blocked_vendor(self):
        self.assertIn('vendor_approved',self.failures(self.run_fields(dict(vendor='Blocked Supplies Ltd',tax_id='BLOCK-TAX-003',po_number='PO-3001'))))
    def test_missing_total(self):
        self.assertEqual(self.run_fields(dict(total=''))['status'],'REVIEW')
    def test_tax_math(self):
        self.assertIn('tax_math',self.failures(self.run_fields(dict(total='650'))))
    def test_negative_credit_note(self):
        self.assertIn('positive_total',self.failures(self.run_fields(dict(total='-600'))))
    def test_future_date(self):
        self.assertIn('dates',self.failures(self.run_fields(dict(invoice_date='2099-01-01'))))
    def test_line_arithmetic(self):
        self.assertIn('line_math',self.failures(self.run_fields(dict(items=[dict(description='Work',quantity='2',unit_price='100',amount='500')]))))
    def test_ocr_requires_review_and_can_be_verified(self):
        r=self.run_fields(ocr=True);self.assertIn('ocr_verification',self.failures(r))
        r=self.service.decide(r['id'],r['fields'],'Verified against source',True);self.assertEqual(r['status'],'APPROVED')
    def test_conflicting_values(self):
        self.assertIn('document_conflicts',self.failures(self.run_fields(conflicts=['total'])))
    def test_review_revalidates_budget(self):
        held=self.run_fields(dict(invoice_number='HELD'),ocr=True)
        self.run_fields()
        r=self.service.decide(held['id'],held['fields'],'Verified original source',True)
        self.assertIn('budget',self.failures(r))
    def test_cannot_approve_twice(self):
        r=self.run_fields()
        with self.assertRaises(ValueError):self.service.decide(r['id'],r['fields'],'Again',True)
    def test_reject_does_not_reserve(self):
        r=self.run_fields(ocr=True);self.service.reject(r['id'],'Invalid source')
        self.assertEqual(self.store.get(r['id'])['status'],'REJECTED')
        self.assertEqual(self.run_fields()['status'],'APPROVED')
    def test_concurrent_reservation(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda number:self.run_fields(dict(invoice_number=number)),['A','B']))
        self.assertEqual(sorted(r['status'] for r in results),['APPROVED','REVIEW'])
    def test_invalid_pdf_rejected(self):
        with self.assertRaises(ValueError):self.service.submit(b'not pdf','x.pdf')
    def test_malformed_pdf_is_failed(self):
        rid=self.service.submit(b'%PDF-broken','x.pdf');self.service.process(rid)
        self.assertEqual(self.store.get(rid)['status'],'REJECTED')
    def test_actual_pdf_end_to_end(self):
        rid=self.service.submit((ROOT/'samples/01-happy-path.pdf').read_bytes(),'happy.pdf');self.service.process(rid)
        r=self.store.get(rid);self.assertEqual(r['status'],'APPROVED',r['decision']);self.assertEqual(len(r['fields']['items']),1)
    def test_extract_conflicts(self):
        f,e,c=extract('Grand Total: 600.00\nGrand Total: 700.00\n');self.assertEqual(c,['total'])
    def test_decimal_precision(self):
        self.assertEqual(money('1,000.01'),100001)
        for value in ['NaN','1.001','1e3','1.000,00','1,00,00']:
            with self.assertRaises(ValueError):money(value)
    def test_scan_dependency_failure_is_actionable(self):
        with patch('app.service.shutil.which',return_value=None):
            with self.assertRaisesRegex(ValueError,'OCR'):read_pdf(ROOT/'samples/09-scanned-invoice.pdf')
    def test_encrypted_pdf(self):
        from pypdf import PdfWriter
        writer=PdfWriter();writer.add_blank_page(100,100);writer.encrypt('secret')
        path=Path(self.temp.name)/'encrypted.pdf'
        with path.open('wb') as f:writer.write(f)
        with self.assertRaisesRegex(ValueError,'Password'):read_pdf(path)

    def test_restart_recovers_incomplete_upload(self):
        rid=self.service.submit((ROOT/'samples/01-happy-path.pdf').read_bytes(),'recover.pdf')
        with self.store.connect() as c:c.execute("UPDATE runs SET status='PROCESSING' WHERE id=?",(rid,))
        recovered=Service(self.store)
        recovered.queue.join()
        recovered.stop()
        self.assertEqual(self.store.get(rid)['status'],'APPROVED')
        again=Service(self.store);again.queue.join();again.stop()
        with self.store.connect() as c:self.assertEqual(c.execute("SELECT reserved_minor FROM purchase_orders WHERE number='PO-1001'").fetchone()[0],60000)

    def test_all_prepared_text_inputs(self):
        expected=['APPROVED','REVIEW','REJECTED','REVIEW','REVIEW','REVIEW','REVIEW','APPROVED','REVIEW']
        files=[p for p in sorted((ROOT/'samples').glob('*.pdf')) if not p.name.startswith('09')]
        for path,status in zip(files,expected):
            rid=self.service.submit(path.read_bytes(),path.name);self.service.process(rid)
            self.assertEqual(self.store.get(rid)['status'],status,path.name)

    def test_empty_normalized_invoice_reference(self):
        self.assertIn('invoice_identity',self.failures(self.run_fields(dict(invoice_number='///'))))

    @unittest.skipUnless(__import__('shutil').which('tesseract') and __import__('shutil').which('pdftoppm'),'OCR binaries not available')
    def test_real_ocr(self):
        rid=self.service.submit((ROOT/'samples/09-scanned-invoice.pdf').read_bytes(),'scan.pdf');self.service.process(rid)
        run=self.store.get(rid)
        self.assertEqual(run['status'],'REVIEW');self.assertTrue(run['ocr'])
        self.assertEqual(run['fields']['invoice_number'],'NS-SCAN-009')
        self.assertEqual(self.service.decide(rid,run['fields'],'Verified scan against source',True)['status'],'APPROVED')

if __name__=='__main__':unittest.main()
