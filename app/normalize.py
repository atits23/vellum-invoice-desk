"""Conservative multilingual label extraction; invoice text is never executable."""
import re
from datetime import datetime
from decimal import Decimal
from difflib import SequenceMatcher

LABELS={
 'vendor':['Vendor','Supplier','From','विक्रेता'], 'tax_id':['Tax ID','GSTIN','VAT ID'],
 'invoice_number':['Invoice Number','Invoice No.','Invoice No','Invoice #','Invoice ID','चालान संख्या'],
 'invoice_date':['Invoice Date','Date','चालान दिनांक'], 'due_date':['Due Date'],
 'po_number':['PO','PO Number','PO No','Purchase Order','Purchase Order Number'],
 'currency':['Currency','मुद्रा'], 'subtotal':['Subtotal','Sub Total','Net Amount','Taxable Amount'],
 'tax':['Tax','VAT','GST','Total Tax'], 'cgst':['CGST'], 'sgst':['SGST'], 'igst':['IGST'],
 'total':['Grand Total','Total Due','Amount Due','Total','कुल राशि'],
 'discount':['Discount'], 'shipping':['Shipping','Freight'], 'round_off':['Round Off','Round-off','Rounding'],
 'document_type':['Document Type'],
}
MONEY_FIELDS={'subtotal','tax','total','cgst','sgst','igst','discount','shipping','round_off'}

def normalize_date(value):
    for fmt in ['%Y-%m-%d','%d/%m/%Y','%d-%m-%Y','%d.%m.%Y','%d %b %Y','%d %B %Y','%b %d, %Y']:
        try:return datetime.strptime(value.strip(),fmt).date().isoformat()
        except ValueError:pass
    return value

def clean_amount(value):
    return re.sub(r'^(?:USD|EUR|GBP|INR|Rs\.?|₹|\$|€|£)\s*','',value.strip(),flags=re.I).strip()

def extract(text):
    fields,evidence,conflicts={},{},[]
    for key,labels in LABELS.items():
        pattern=r'^[ \t]*(?:'+ '|'.join(re.escape(label) for label in sorted(labels,key=len,reverse=True))+r')[ \t]*(?::|#|\s+-\s+)[ \t]*(.*?)[ \t]*$'
        matches=list(re.finditer(pattern,text,re.I|re.M))
        values=list(dict.fromkeys(m[1].strip() for m in matches if m[1].strip()))
        if values:
            value=values[0]
            if key in MONEY_FIELDS:value=clean_amount(value)
            if key.endswith('_date'):value=normalize_date(value)
            if key=='currency':value='INR' if value.strip().upper() in ['RS.','RS','₹','INR'] else value.upper()
            fields[key]=value;evidence[key]=matches[0][0].strip()
        if len(values)>1:conflicts.append(key)
    if 'currency' not in fields and re.search(r'(?:₹|\bRs\.)',text):fields['currency']='INR';evidence['currency']='Explicit rupee symbol in document'
    if re.search(r'\bCREDIT\s+NOTE\b',text,re.I):fields['document_type']='CREDIT NOTE'
    elif re.search(r'\bPRO\s*FORMA\b',text,re.I):fields['document_type']='PROFORMA'
    elif re.search(r'^\s*(?:MEETING AGENDA|RESUME|CURRICULUM VITAE|PURCHASE ORDER ONLY)\b',text,re.I):fields['document_type']='NON-INVOICE'
    elif not re.search(r'\binvoice\b|चालान',text,re.I):fields['document_type']='UNCLASSIFIED'
    else:fields.setdefault('document_type','INVOICE')
    items=[]
    for line in text.splitlines():
        parts=[p.strip() for p in line.split('|')]
        if len(parts) not in (4,5) or not re.fullmatch(r'\d+(?:\.\d+)?',parts[1]):continue
        if not all(re.fullmatch(r'[\d,]+(?:\.\d{1,2})?',clean_amount(p)) for p in parts[2:4]):continue
        items.append(dict(description=parts[0],quantity=parts[1],unit_price=clean_amount(parts[2]),amount=clean_amount(parts[3]),unit=parts[4] if len(parts)==5 else 'each'))
    fields['items']=items
    return fields,evidence,conflicts

ALIASES={'notebook computer':'laptop','notebook pc':'laptop','laptop computer':'laptop','cloud platform subscription':'cloud subscription','cloud service':'cloud subscription'}
def semantic_match(left,right):
    def canonical(s):
        s=re.sub(r'[^a-z0-9 ]',' ',s.lower());s=' '.join(s.split())
        return ALIASES.get(s,s)
    a,b=canonical(left),canonical(right)
    if a==b:return 1.0,'exact or curated synonym'
    tokens_a,tokens_b=set(a.split()),set(b.split())
    overlap=len(tokens_a&tokens_b)/max(1,len(tokens_a|tokens_b))
    return round(.5*SequenceMatcher(None,a,b).ratio()+.5*overlap,3),'token overlap + character similarity'
