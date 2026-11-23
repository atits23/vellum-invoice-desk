"""Conservative multilingual label extraction; invoice text is never executable."""
import re
from datetime import datetime
from decimal import Decimal
from difflib import SequenceMatcher

LABELS={
 'vendor':['Vendor','Supplier','From','विक्रेता'], 'tax_id':['Tax ID','GSTIN','VAT ID'],
 'invoice_number':['Invoice Number','Invoice No.','Invoice No','Invoice #','Invoice ID','चालान संख्या'],
 'invoice_date':['Invoice Date','Date','चालान दिनांक'], 'due_date':['Due Date'],
 'po_number':['PO','PO Number','PO No','PO Reference','Purchase Order','Purchase Order Number'],
 'currency':['Currency','मुद्रा'], 'subtotal':['Subtotal','Sub Total','Net Amount','Taxable Amount','Sub-total','Total Before Tax'],
 'tax':['Tax','VAT','GST','Total Tax'], 'cgst':['CGST'], 'sgst':['SGST'], 'igst':['IGST'],
 'total':['Grand Total','Total Due','Amount Due','Balance Due','Net Total','Total','कुल राशि'],
 'discount':['Discount'], 'shipping':['Shipping','Freight'], 'round_off':['Round Off','Round-off','Rounding'],
 'document_type':['Document Type'],
}
MONEY_FIELDS={'subtotal','tax','total','cgst','sgst','igst','discount','shipping','round_off'}

def normalize_date(value):
    for fmt in ['%Y-%m-%d','%d/%m/%Y','%d-%m-%Y','%d.%m.%Y','%d %b %Y','%d %B %Y','%b %d, %Y','%m/%d/%y','%m/%d/%Y']:
        try:return datetime.strptime(value.strip(),fmt).date().isoformat()
        except ValueError:pass
    return value

def clean_amount(value):
    return re.sub(r'^(?:USD|EUR|GBP|INR|Rs\.?|₹|\$|€|£)\s*','',value.strip(),flags=re.I).strip()

def extract(text):
    text=text.replace('\u00a0',' ')
    fields,evidence,conflicts={},{},[]
    # Layout-aware PDF extraction preserves horizontal label/value relationships.
    # OCR sometimes wraps the value to the following line; accept one adjacent line.
    for key,labels in LABELS.items():
        pattern=r'^[ \t]*(?:'+ '|'.join(re.escape(label) for label in sorted(labels,key=len,reverse=True))+r')(?:[ \t]*[:#][ \t]*|[ \t]+|[ \t]*\n[ \t]*)([^\n]*?)\s*$'
        matches=list(re.finditer(pattern,text,re.I|re.M))
        values=[];sources=[]
        for match in matches:
            heading=match[0].lstrip()
            owners=[(len(label),owner) for owner,names in LABELS.items() for label in names if re.match(re.escape(label)+r'(?=\s|:|#|$)',heading,re.I)]
            if owners and max(owners,key=lambda item:item[0])[1]!=key:continue
            value=match[1].strip()
            if not value:continue
            if key in MONEY_FIELDS:
                # Monetary values are conventionally the final numeric column, not a qty or tax percentage.
                numbers=re.findall(r'(?<![A-Za-z])[-+]?(?:\d[\d.,]*\d|\d)(?![A-Za-z])',value)
                if numbers and not value.endswith('%'):
                    value=clean_amount(numbers[-1]).rstrip('.,')
                    if re.fullmatch(r'-?\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?',value):
                        value=value.replace('.','').replace(',','.')
                        if fields.get('currency') not in ('IDR','EUR'):conflicts.append('numeric_locale')
                    elif re.fullmatch(r'-?\d+(?:\.\d{3})*,\d{1,2}',value):value=value.replace('.','').replace(',','.')
                else:value=clean_amount(value)
            if key.endswith('_date'):value=normalize_date(value)
            if key=='currency':value='INR' if value.upper() in ['RS.','RS','₹','INR'] else value.upper()
            if value not in values:values.append(value);sources.append(match[0].strip())
        if values:fields[key]=values[0];evidence[key]=sources[0]
        if len(values)>1:conflicts.append(key)
    if 'currency' not in fields:
        for currency,pattern in [('INR',r'₹|\bRs\.'),('EUR',r'€|\bEUR\b'),('USD',r'\bUSD\b'),('IDR',r'\bRp[ .:]|\bIDR\b')]:
            if re.search(pattern,text,re.I):fields['currency']=currency;evidence['currency']='Explicit currency notation in source';break
    # Invoice identifiers next to a heading are common even without an explicit label.
    if not fields.get('invoice_number'):
        match=re.search(r'\bInvoice\s+(?:#\s*)?([A-Z][A-Z0-9/-]*\d[A-Z0-9/-]*|\d[\d/-]+)\b',text,re.I)
        if match:fields['invoice_number']=match[1];evidence['invoice_number']=match[0]
    if not fields.get('vendor'):
        # Only explicit legal-business headers are candidates; inferred identity still needs review.
        for line in text.splitlines()[:12]:
            line=line.strip()
            if re.search(r'\b(?:Ltd\.?|Limited|LLC|Inc\.?|GmbH|Pvt\.?|Private Limited)\b',line,re.I) and len(line)<100:
                fields['vendor']=line;evidence['vendor']=line;conflicts.append('inferred_vendor');break
    explicit=fields.get('document_type','').upper()
    if re.search(r'\bCREDIT\s+NOTE\b',text,re.I):fields['document_type']='CREDIT NOTE'
    elif re.search(r'\bPRO\s*FORMA\b',text,re.I):fields['document_type']='PROFORMA'
    elif explicit in ('QUOTATION','DELIVERY CHALLAN','BANK STATEMENT','RESUME') or re.search(r'^\s*(?:MEETING AGENDA|RESUME|CURRICULUM VITAE|BANK STATEMENT|QUOTATION|DELIVERY CHALLAN|PURCHASE ORDER ONLY)\b',text,re.I|re.M):fields['document_type']='NON-INVOICE'
    elif not re.search(r'\binvoice\b|चालान',text,re.I):fields['document_type']='UNCLASSIFIED'
    else:fields.setdefault('document_type','INVOICE')
    if re.search(r'\bTDS\b|tax[- ]inclusive|prices?\s+include\s+(?:GST|VAT|tax)',text,re.I):conflicts.append('tax_treatment_requires_review')
    if len(set(re.findall(r'\bPO[ -]?[A-Z0-9-]*\d[A-Z0-9-]*',text,re.I)))>1:conflicts.append('multiple_po_references')
    items=[];pending=[]
    for line in text.splitlines():
        parts=[p.strip() for p in line.split('|')]
        if len(parts) not in (4,5):
            m=re.match(r'^\s*(.+?)\s{2,}(\d+(?:\.\d+)?)\s+(?:([\d,.]+))\s+([\d,.]+)(?:\s+(each|hour|pcs|box))?\s*$',line)
            if m:parts=[m[1],m[2],m[3],m[4],m[5] or 'each']
        if len(parts) not in (4,5) or not re.fullmatch(r'\d+(?:\.\d+)?',parts[1]):continue
        if not all(re.fullmatch(r'[\d,]+(?:\.\d{1,2})?',clean_amount(p)) for p in parts[2:4]):continue
        items.append(dict(description=parts[0],quantity=parts[1],unit_price=clean_amount(parts[2]),amount=clean_amount(parts[3]),unit=parts[4] if len(parts)==5 else 'each'))
    fields['items']=items
    return fields,evidence,list(dict.fromkeys(conflicts))

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
