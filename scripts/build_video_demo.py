"""Create fictional video fixtures and verify their ordered decisions in an isolated store."""
import sys,json,tempfile
from pathlib import Path
from datetime import date
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
from app.store import Store
from app.service import Service
OUT=ROOT/'output/pdf/video-edge-case';OUT.mkdir(parents=True,exist_ok=True)
cases=[
 ('01-approved-first-invoice.pdf','VIDEO-001','Acme Cloud Services','ACME-TAX-001','PO-1001','500.00','100.00','600.00','APPROVED'),
 ('02-one-cent-over-remaining.pdf','VIDEO-002','Acme Cloud Services','ACME-TAX-001','PO-1001','350.01','70.00','420.01','REVIEW'),
 ('03-reformatted-duplicate.pdf','VIDEO/001','Acme Cloud Services','ACME-TAX-001','PO-1001','500.00','100.00','600.00','REJECTED'),
 ('04-blocked-vendor.pdf','VIDEO-BLOCK-004','Blocked Supplies Ltd','BLOCK-TAX-003','PO-3001','500.00','100.00','600.00','REVIEW'),
 ('05-exact-boundary-approved.pdf','VIDEO-005','Acme Cloud Services','ACME-TAX-001','PO-1001','350.00','70.00','420.00','APPROVED'),
]
for filename,number,vendor,taxid,po,sub,tax,total,expected in cases:
 c=canvas.Canvas(str(OUT/filename),pagesize=(595,842));c.setTitle('Fictional Vellum video invoice '+number)
 c.setFillColor(HexColor('#f4f4f4'));c.rect(0,0,595,842,fill=1,stroke=0)
 c.setFillColor(HexColor('#20211d'));c.setFont('Helvetica-Bold',30);c.drawString(44,775,'INVOICE')
 c.setFont('Helvetica',11);c.drawString(44,746,'VELLUM / FICTIONAL VIDEO DEMONSTRATION')
 if 'duplicate' in filename:c.drawString(44,718,'Reissued copy - invoice reference punctuation reformatted')
 rows=[('Vendor',vendor),('Tax ID',taxid),('Invoice Number',number),('Invoice Date',date.today().isoformat()),('PO',po),('Currency','USD'),('Subtotal',sub),('Tax',tax),('Grand Total',total)]
 for i,(label,value) in enumerate(rows):
  y=660-i*45;c.setFont('Helvetica-Bold' if label=='Grand Total' else 'Helvetica',13);c.drawString(44,y,label+': '+value)
 c.setFont('Helvetica',10);c.drawString(44,130,'Fictional data. No payment requested. Amounts shown in USD.')
 c.drawString(44,110,'This sample tests header, identity and budget controls; no item lines supplied.')
 c.save()
results=[]
with tempfile.TemporaryDirectory() as directory:
 service=Service(Store(directory),start_worker=False)
 for filename,*_,expected in cases:
  rid=service.submit((OUT/filename).read_bytes(),filename);service.process(rid);run=service.store.get(rid)
  assert run['status']==expected,(filename,run)
  results.append({'file':filename,'expected':expected,'actual':run['status'],'failed_checks':[r for r in run['decision']['rules'] if not r['passed']]})
 with service.store.connect() as c:assert c.execute("SELECT reserved_minor FROM purchase_orders WHERE number='PO-1001'").fetchone()[0]==102000
(OUT/'verified-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
print(json.dumps(results,indent=2))
