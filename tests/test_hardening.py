import unittest
import test_workflow as workflow
from app.normalize import extract

class Hardening(unittest.TestCase):
    setUp=workflow.Workflow.setUp
    tearDown=workflow.Workflow.tearDown
    run_fields=workflow.Workflow.run_fields

    def test_hostile_size_empty_and_executable(self):
        class Oversize(bytes):
            def __len__(self):return 200*1024*1024
        for body in [b'',b'MZ executable disguised as invoice.pdf',Oversize(b'%PDF-1.4')]:
            with self.assertRaises(ValueError):self.service.submit(body,'invoice.pdf')
        with self.store.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM runs').fetchone()[0],0)

    def test_override_reservation_is_reversible_and_not_double_counted(self):
        run=self.run_fields();rid=run['id']
        for status,expected in [('APPROVED',60000),('REVIEW',0),('APPROVED',60000),('REJECTED',0)]:
            result=self.service.override(rid,status,'Explicit exception checked','admin-test')
            self.assertTrue(result['decision']['manual_override'])
            with self.store.connect() as c:self.assertEqual(c.execute("SELECT reserved_minor FROM purchase_orders WHERE number='PO-1001'").fetchone()[0],expected)

    def test_override_requires_note_and_valid_po_amount(self):
        run=self.run_fields({'total':'','subtotal':''})
        with self.assertRaises(ValueError):self.service.override(run['id'],'APPROVED','Verified exception','admin')
        with self.assertRaises(ValueError):self.service.override(run['id'],'REJECTED',' ','admin')

    def test_layout_label_ownership_and_european_amount(self):
        fields,_,_=extract('Tax ID: GST-123\nCurrency: EUR\nSubtotal     1.000,00\nTax     200,00\nGrand Total     1.200,00')
        self.assertEqual(fields['tax_id'],'GST-123');self.assertEqual(fields['tax'],'200.00');self.assertEqual(fields['total'],'1200.00')

    def test_multiple_invoice_references_are_conflicted(self):
        _,_,conflicts=extract('Invoice Number: A-1\nInvoice Number: B-2\nGrand Total: 100\nGrand Total: 200')
        self.assertIn('invoice_number',conflicts);self.assertIn('total',conflicts)
