"""Generate fictional, reproducible invoice inputs; never seed fake run results."""
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'samples'
OUT.mkdir(exist_ok=True)
BASE = dict(vendor='Acme Cloud Services',tax_id='ACME-TAX-001',invoice_number='AC-2026-001',invoice_date='2026-10-15',due_date='2026-11-15',po_number='PO-1001',currency='USD',subtotal='500.00',tax='100.00',total='600.00')
LABELS = dict(vendor='Vendor',tax_id='Tax ID',invoice_number='Invoice Number',invoice_date='Invoice Date',due_date='Due Date',po_number='PO',currency='Currency',subtotal='Subtotal',tax='Tax',total='Grand Total')

def make(name, changes=None, duplicate=False, scan=False):
    f = {**BASE,**(changes or {})}
    lines = [f'{LABELS[k]}: {v}' for k,v in f.items() if v]
    if name == '01-happy-path.pdf':
        lines += ['Cloud platform subscription | 5 | 100.00 | 500.00']
    if duplicate:
        lines += ['Reissued copy for accounts payable. Please retain for your records.']
    c = canvas.Canvas(str(OUT/name),pagesize=(595,842),invariant=True)
    c.setTitle('Fictional invoice - '+name)
    if scan:
        image = Image.new('RGB',(1190,1684),'white')
        draw = ImageDraw.Draw(image)
        candidates = ['C:/Windows/Fonts/arial.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']
        fontpath = next((p for p in candidates if Path(p).exists()),None)
        font = ImageFont.truetype(fontpath,28) if fontpath else ImageFont.load_default(size=28)
        draw.text((100,100),'INVOICE',font=font,fill='black')
        for i,line in enumerate(lines):
            draw.text((100,220+i*65),line,font=font,fill='black')
        from reportlab.lib.utils import ImageReader
        c.drawImage(ImageReader(image),0,0,width=595,height=842)
    else:
        c.setFillColor(HexColor('#102d37'));c.rect(0,710,595,132,fill=1,stroke=0)
        c.setFillColor(HexColor('#ffffff'));c.setFont('Helvetica-Bold',30);c.drawString(48,774,'INVOICE')
        c.setFont('Helvetica',11);c.drawString(48,747,'Fictional sample · Invoice Desk case study')
        c.setFillColor(HexColor('#213d48'))
        for i,line in enumerate(lines):
            c.setFont('Helvetica-Bold' if line.startswith('Grand Total') else 'Helvetica',12 if len(line)<70 else 10)
            c.drawString(48,666-i*33,line)
        c.setStrokeColor(HexColor('#d2e2e7'));c.line(48,145,547,145)
        c.setFont('Helvetica',10);c.drawString(48,122,'Bill to: Acme Operations | Accounts Payable')
        c.drawString(48,102,'No payment requested. Test document only.')
    c.save()

if __name__ == '__main__':
    make('01-happy-path.pdf')
    make('02-split-over-budget.pdf',dict(invoice_number='AC-2026-002',subtotal='400.00',tax='80.00',total='480.00'))
    make('03-semantic-duplicate.pdf',dict(invoice_number='AC/2026/001'),duplicate=True)
    make('04-ambiguous-po.pdf',dict(vendor='Northstar Design Studio',tax_id='NORTH-TAX-002',invoice_number='NS-001',po_number=''))
    make('05-tax-mismatch.pdf',dict(invoice_number='AC-TAX-005',total='650.00'))
    make('06-missing-total.pdf',dict(invoice_number='AC-MISSING-006',total=''))
    make('07-blocked-vendor.pdf',dict(vendor='Blocked Supplies Ltd',tax_id='BLOCK-TAX-003',invoice_number='BS-007',po_number='PO-3001'))
    make('08-unique-inferred-po.pdf',dict(invoice_number='AC-INFER-008',po_number='',subtotal='100.00',tax='20.00',total='120.00'))
    make('09-scanned-invoice.pdf',dict(invoice_number='NS-SCAN-009',vendor='Northstar Design Studio',tax_id='NORTH-TAX-002',po_number='PO-2001'),scan=True)
    make('10-currency-mismatch.pdf',dict(invoice_number='AC-EUR-010',currency='EUR'))
    print('Generated 10 invoice PDFs in',OUT)
