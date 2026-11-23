"""Deterministic extraction and financial controls. No network/model dependency."""
import re
import unicodedata
import json
from datetime import date
from decimal import Decimal, InvalidOperation

VERSION = '2026.2'
CURRENCIES = {'USD', 'EUR', 'GBP', 'INR'}

def norm(value):
    return re.sub(r'[^A-Z0-9]', '', unicodedata.normalize('NFKC', str(value)).upper())

def money(value):
    raw = str(value).strip()
    from app.normalize import clean_amount
    raw=clean_amount(raw)
    if ',' in raw and not (re.fullmatch(r'-?\d{1,3}(?:,\d{3})+(?:\.\d{1,2})?', raw) or re.fullmatch(r'-?\d{1,2}(?:,\d{2})*,\d{3}(?:\.\d{1,2})?',raw)):
        raise ValueError('Ambiguous thousands separator.')
    raw = raw.replace(',', '')
    if not re.fullmatch(r'-?\d+(?:\.\d{1,2})?', raw):
        raise ValueError('Use an unambiguous amount with at most two decimal places.')
    try:
        result = Decimal(raw) * 100
        if abs(result) > 10**12:
            raise ValueError('Amount exceeds supported limit.')
        return int(result)
    except InvalidOperation as exc:
        raise ValueError('Invalid amount') from exc

def extract(text):
    patterns = {
        'vendor': r'(?:Vendor|Supplier|From)\s*:\s*(.+)',
        'tax_id': r'(?:Tax ID|GSTIN|VAT ID)\s*:\s*(.+)',
        'invoice_number': r'(?:Invoice\s*(?:Number|No\.?|#))\s*:?\s*(\S+)',
        'invoice_date': r'(?:Invoice Date|Date)\s*:\s*(\d{4}-\d{2}-\d{2})',
        'due_date': r'Due Date\s*:\s*(\d{4}-\d{2}-\d{2})',
        'po_number': r'(?:PO|Purchase Order)\s*(?:Number|No\.?|#)?\s*:\s*(\S+)',
        'currency': r'Currency\s*:\s*([A-Z]{3})',
        'subtotal': r'(?:Subtotal|Net Amount)\s*:\s*([\d,]+(?:\.\d{1,2})?)',
        'tax': r'(?:Tax|VAT|GST)\s*:\s*([\d,]+(?:\.\d{1,2})?)',
        'total': r'(?:Grand Total|Total Due|Amount Due|Total)\s*:\s*([\d,]+(?:\.\d{1,2})?)',
    }
    fields, evidence, conflicts = {}, {}, []
    for key, pattern in patterns.items():
        matches = list(re.finditer(r'^\s*' + pattern + r'\s*$', text, re.I | re.M))
        values = list(dict.fromkeys(m.group(1).strip() for m in matches))
        if values:
            fields[key] = values[0]
            evidence[key] = matches[0].group(0).strip()
        if len(values) > 1:
            conflicts.append(key)
    # Supported line syntax keeps quantity, unit price and extension independently auditable.
    items = []
    for m in re.finditer(r'^(.+?)\s+\|\s*(\d+(?:\.\d+)?)\s*\|\s*([\d,]+(?:\.\d{1,2})?)\s*\|\s*([\d,]+(?:\.\d{1,2})?)\s*$', text, re.M):
        items.append(dict(description=m[1].strip(), quantity=m[2], unit_price=m[3], amount=m[4]))
    fields['items'] = items
    return fields, evidence, conflicts

from app.normalize import extract, normalize_date, semantic_match

def evaluate(conn, run_id, fields, digest, ocr=False, conflicts=None, verified=False):
    rules = []
    def check(code, passed, message):
        rules.append({'code': code, 'passed': bool(passed), 'message': message})
    policy=dict(conn.execute('SELECT * FROM policy WHERE id=1').fetchone())
    def allowance(p):return max(int(Decimal(str(policy['tolerance_percent']))*p['amount_minor']/100),money(str(policy['tolerance_absolute'])))
    document_type=fields.get('document_type','INVOICE').upper()
    check('document_type',document_type=='INVOICE','Document type: '+document_type+'. Credit notes and proforma invoices need a separate verified workflow.')
    required = ['vendor', 'invoice_number', 'invoice_date', 'currency', 'total']
    missing = [key for key in required if not str(fields.get(key, '')).strip()]
    check('required_fields', not missing, 'Required fields present.' if not missing else 'Missing: ' + ', '.join(missing))
    check('invoice_identity', bool(norm(fields.get('invoice_number',''))), 'Invoice reference must contain letters or digits.')
    check('document_conflicts', not conflicts or verified, 'Document values verified.' if verified else ('Conflicting values: ' + ', '.join(conflicts or []) if conflicts else 'No conflicting extracted values.'))
    check('ocr_verification', not ocr or verified, 'Scan verified by reviewer.' if verified and ocr else ('OCR requires source verification.' if ocr else 'Machine-readable source.'))
    currency = str(fields.get('currency', '')).upper()
    check('currency', currency in CURRENCIES, 'Currency: ' + (currency or 'missing'))
    try:
        inv_date = date.fromisoformat(normalize_date(fields.get('invoice_date', '')))
        due = date.fromisoformat(normalize_date(fields['due_date'])) if fields.get('due_date') else inv_date
        check('dates', inv_date <= date.today() and due >= inv_date, 'Invoice must not be future-dated; due date must follow invoice date.')
        check('invoice_age',(date.today()-inv_date).days<=365,'Invoices older than 365 days require review.')
    except (ValueError, TypeError):
        check('dates', False, 'Use valid ISO dates (YYYY-MM-DD).')
    total = None
    try:
        total = money(fields.get('total', ''))
        check('positive_total', total > 0, 'Total must be positive; credit notes require a separate workflow.')
        components=[money(fields[k]) for k in ['cgst','sgst','igst'] if fields.get(k)]
        if fields.get('subtotal') and (fields.get('tax') or components):
            sub = money(fields['subtotal']);tax=money(fields['tax']) if fields.get('tax') else sum(components)
            discount=money(fields.get('discount') or '0');shipping=money(fields.get('shipping') or '0');round_off=money(fields.get('round_off') or '0')
            check('tax_math', sub >= 0 and tax >= 0 and discount>=0 and shipping>=0 and abs(round_off)<=100 and abs(sub-discount+shipping+tax+round_off-total)<=1, 'Subtotal − discount + shipping + tax + round-off must equal total (one-cent tolerance; round-off capped at 1 currency unit).')
            if components:
                check('gst_components',not(fields.get('igst') and (fields.get('cgst') or fields.get('sgst'))) and (not fields.get('tax') or abs(sum(components)-tax)<=1),'Use either IGST or CGST/SGST; components must sum to total tax.')
                if fields.get('cgst') or fields.get('sgst'):check('gst_split',abs(money(fields.get('cgst','0'))-money(fields.get('sgst','0')))<=1,'CGST and SGST must be equal within one cent.')
        else:
            check('tax_math', False, 'Provide subtotal and tax explicitly, including zero tax for exempt invoices.')
        items = fields.get('items', [])
        if items:
            check('line_math', all(abs(Decimal(i['quantity']) * money(i['unit_price']) - money(i['amount'])) <= 1 and Decimal(i['quantity']) > 0 for i in items), 'Each quantity × unit price must match the line amount.')
            check('line_sum', abs(sum(money(i['amount']) for i in items) - money(fields.get('subtotal', ''))) <= 1, 'Line amounts must sum to subtotal.')
    except (ValueError, InvalidOperation, KeyError, TypeError):
        check('amount_format', False, 'Invalid or ambiguous monetary values.')
    vendors = [dict(r) for r in conn.execute('SELECT * FROM vendors')]
    matches = [v for v in vendors if norm(v['name']) == norm(fields.get('vendor', ''))]
    variant=False
    if not matches and fields.get('tax_id'):
        matches=[v for v in vendors if norm(v['tax_id'])==norm(fields['tax_id'])];variant=bool(matches)
    vendor = matches[0] if len(matches) == 1 else None
    check('vendor_identity', vendor is not None, 'Vendor matched exactly.' if vendor else 'Vendor name is unknown or ambiguous; verify against master data.')
    po, duplicate = None, None
    if vendor:
        check('vendor_name_variant',not variant or verified,'Vendor name variant matched by tax ID; verify legal name.' if variant else 'Exact normalized vendor name.')
        check('vendor_approved', vendor['approved'] == 1, 'Vendor is approved.' if vendor['approved'] else 'Vendor is blocked in procurement.')
        check('tax_identity', bool(fields.get('tax_id')) and norm(fields.get('tax_id', '')) == norm(vendor['tax_id']), 'Vendor tax ID must match procurement master data.')
        duplicate = conn.execute("SELECT id FROM runs WHERE id != ? AND status IN ('APPROVED','REVIEW') AND (digest = ? OR (vendor_id = ? AND invoice_key = ?)) ORDER BY created_at LIMIT 1", (run_id, digest, vendor['id'], norm(fields.get('invoice_number', '')))).fetchone()
    else:
        duplicate = conn.execute("SELECT id FROM runs WHERE id != ? AND digest = ? AND status IN ('APPROVED','REVIEW') LIMIT 1", (run_id, digest)).fetchone()
    check('duplicate', duplicate is None, 'Duplicate of run ' + duplicate['id'] if duplicate else 'No active duplicate found.')
    if vendor and total is not None:
        suspicious=[]
        for previous in conn.execute("SELECT id,fields FROM runs WHERE id!=? AND vendor_id=? AND status='APPROVED'",(run_id,vendor['id'])):
            old=json.loads(previous['fields'])
            try:
                if money(old.get('total',''))==total and norm(old.get('invoice_number',''))!=norm(fields.get('invoice_number','')) and old.get('invoice_date')==fields.get('invoice_date') and old.get('currency')==fields.get('currency'):suspicious.append(previous['id'])
            except ValueError:pass
        check('suspicious_repeat',not suspicious or verified,'Same vendor, date and amount with another reference; verify separate delivery.' if suspicious else 'No suspicious same-value repeat.')
    if vendor and currency in CURRENCIES and total is not None:
        if fields.get('po_number'):
            pos = [dict(p) for p in conn.execute('SELECT * FROM purchase_orders') if norm(p['number']) == norm(fields['po_number'])]
            po = pos[0] if len(pos) == 1 else None
            check('po_match', po is not None, 'Explicit PO matched.' if po else 'Explicit PO is unknown; no automatic substitution.')
        else:
            pos = [dict(p) for p in conn.execute("SELECT * FROM purchase_orders WHERE vendor_id=? AND currency=? AND state='OPEN'", (vendor['id'], currency)) if total <= p['amount_minor'] + allowance(p) - p['reserved_minor'] and (not p['expires'] or p['expires']>=date.today().isoformat())]
            po = pos[0] if len(pos) == 1 else None
            check('po_match', po is not None, 'Inferred unique eligible PO.' if po else f'{len(pos)} eligible POs; an explicit reference is required.')
        if po:
            check('po_vendor', po['vendor_id'] == vendor['id'], 'PO must belong to the invoicing vendor.')
            check('po_currency', po['currency'] == currency, 'Invoice and PO currencies must match; no implicit FX conversion.')
            check('po_open', po['state'] == 'OPEN', 'PO must be open.')
            check('po_expiry',not po.get('expires') or po['expires']>=date.today().isoformat(),'PO must not be expired.')
            remaining = po['amount_minor'] + allowance(po) - po['reserved_minor']
            variance=max(0,po['reserved_minor']+total-po['amount_minor'])
            check('budget', 0 < total <= remaining, f'Gross requested {total / 100:.2f}; available {remaining / 100:.2f} {po["currency"]}. Cumulative excess {variance/100:.2f} / {po["amount_minor"]/100:.2f} = {variance/max(1,po["amount_minor"])*100:.2f}%; tolerance {policy["tolerance_percent"]}% or {policy["tolerance_absolute"]:.2f}, whichever is greater.')
            po['variance_percent']=variance/max(1,po['amount_minor'])*100
            po_lines=[dict(r) for r in conn.execute('SELECT * FROM po_items WHERE po_number=?',(po['number'],))]
            current_quantities={}
            for index,item in enumerate(fields.get('items',[])):
                candidates=sorted([(semantic_match(item['description'],p['description'])[0],p) for p in po_lines],key=lambda t:t[0],reverse=True)
                score,line=candidates[0] if candidates else (0,None)
                check(f'item_{index}_description',score>=.85,f'Item {index+1}: description match confidence {score:.0%}; threshold 85%. Curated synonyms plus lexical similarity, not an embedding model.')
                if line and score>=.85:
                    try:
                        used=Decimal('0')
                        for prior in conn.execute("SELECT fields,decision FROM runs WHERE id!=? AND status='APPROVED'",(run_id,)):
                            pd=json.loads(prior['decision'])
                            if (pd.get('po') or {}).get('number')==po['number']:
                                used+=sum((Decimal(i['quantity']) for i in json.loads(prior['fields']).get('items',[]) if semantic_match(i['description'],line['description'])[0]>=.85),Decimal('0'))
                        key=line['description']
                        current_quantities[key]=current_quantities.get(key,Decimal('0'))+Decimal(item['quantity'])
                        requested=current_quantities[key]
                        check(f'item_{index}_quantity',used+requested<=Decimal(line['quantity']),f'Previously billed {used} + cumulative invoice quantity {requested}; ordered {line["quantity"]}.')
                        check(f'item_{index}_price',money(item['unit_price'])<=money(line['unit_price']),f'Unit price {item["unit_price"]}; PO price {line["unit_price"]}.')
                        check(f'item_{index}_unit',item.get('unit','each').lower()==line['unit'].lower(),f'Unit {item.get("unit","each")}; PO unit {line["unit"]}. No implicit unit conversion.')
                    except (ValueError,KeyError,InvalidOperation):check(f'item_{index}_data',False,'Invalid item quantity or price.')
    status = 'APPROVED' if all(r['passed'] for r in rules) else 'REVIEW'
    if duplicate or document_type=='NON-INVOICE':status='REJECTED'
    return {'status': status, 'rules': rules, 'vendor_id': vendor['id'] if vendor else None, 'invoice_key': norm(fields.get('invoice_number', '')), 'po': po, 'total_minor': total, 'policy_version': VERSION, 'policy':policy,'next_action': 'Ready for payment scheduling. No payment has been sent.' if status == 'APPROVED' else 'Rejected: confirmed duplicate or non-invoice document. No budget reserved.' if status=='REJECTED' else 'Verify the source and resolve failed checks; correct fields or reject with a reason.'}
