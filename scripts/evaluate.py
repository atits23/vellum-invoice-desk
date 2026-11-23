"""Evaluate immutable ground truth. Does not infer expected outcomes from predictions."""
import csv,json,sys,time,tempfile,statistics,uuid,hashlib,html
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from app.store import Store,now
from app.service import Service
from app.engine import norm,money
from app.normalize import normalize_date

def evaluate(output='evaluation'):
    corpus=ROOT/'tests/corpus';rows=list(csv.DictReader((corpus/'manifest.csv').open(encoding='utf-8')))
    labels=['APPROVED','REVIEW','REJECTED'];matrix={a:{b:0 for b in labels} for a in labels};fields={};results=[]
    preload=json.loads((corpus/'preload.json').read_text())
    for index,row in enumerate(rows):
        path=corpus/row['file'];body=path.read_bytes()
        if hashlib.sha256(body).hexdigest()!=row['sha256']:raise ValueError('Corpus integrity mismatch: '+row['file'])
        with tempfile.TemporaryDirectory() as temp:
            store=Store(temp);service=Service(store,start_worker=False)
            if row['preload']:
                rid=uuid.uuid4().hex
                with store.connect() as c:c.execute('INSERT INTO runs(id,filename,digest,status,created_at,updated_at,fields) VALUES(?,?,?,?,?,?,?)',(rid,'prior.pdf','prior','PROCESSING',now(),now(),json.dumps(preload)))
                service.decide(rid)
            start=time.perf_counter()
            try:
                rid=service.submit(body,path.name);service.process(rid);run=store.get(rid);actual=run['status'];extracted=run['fields'];reason=run.get('error') or '; '.join(r['message'] for r in run['decision'].get('rules',[]) if not r['passed'])
            except ValueError as exc:actual='REJECTED';extracted={};reason=str(exc);run={'metadata':{}}
            duration=(time.perf_counter()-start)*1000
            if actual not in labels:actual='REVIEW'
            expected=row['expected_decision'];matrix[expected][actual]+=1
            truth=json.loads(row['ground_truth_fields']);correct={}
            for key,value in truth.items():
                candidate=extracted.get(key,'')
                if key in ['total','subtotal','tax','cgst','sgst','igst','discount','shipping','round_off']:
                    try:passed=money(candidate)==money(value)
                    except ValueError:passed=str(candidate)==str(value)
                elif key.endswith('_date'):passed=normalize_date(str(candidate))==normalize_date(value)
                else:passed=norm(candidate)==norm(value)
                fields.setdefault(key,{'correct':0,'total':0});fields[key]['correct']+=int(passed);fields[key]['total']+=1;correct[key]=passed
            misses=[k for k,v in correct.items() if not v]
            causes=[]
            if misses:
                missing=[k for k in misses if not extracted.get(k)]
                if missing:causes.append('No extracted candidate for '+', '.join(missing))
                differing=[k for k in misses if extracted.get(k)]
                if differing:causes.append('Extracted value disagrees with independent label: '+', '.join(differing))
                if run['metadata'].get('ocr_confidence',1) is not None and run['metadata'].get('ocr_confidence',1)<.85:causes.append('OCR word confidence below 85%; visual reading needed')
            results.append({'file':row['file'],'expected':expected,'actual':actual,'mode':'ocr' if run['metadata'].get('ocr_confidence') is not None else 'text','group':row['group'],'duration_ms':round(duration,2),'reason':reason,'fields':correct,'field_misses':misses,'causes':causes,'ground_truth':truth,'extracted':{k:extracted.get(k) for k in truth},'ocr_confidence':run['metadata'].get('ocr_confidence')})
        if (index+1)%10==0:print(f'Evaluated {index+1}/{len(rows)}',flush=True)
    n=len(results);safe=sum(r['expected']!='APPROVED' for r in results);false_approves=sum(r['actual']=='APPROVED' and r['expected']!='APPROVED' for r in results)
    routing={}
    for label in labels:
        tp=matrix[label][label];predicted=sum(matrix[a][label] for a in labels);expected=sum(matrix[label].values());routing[label]={'precision':tp/predicted if predicted else None,'recall':tp/expected if expected else None}
    for value in fields.values():value['accuracy']=value['correct']/value['total']
    def slice_report(group):
        subset=[r for r in results if r['group']==group];return {'total':len(subset),'decision_accuracy':sum(r['expected']==r['actual'] for r in subset)/len(subset) if subset else None,'field_accuracy':sum(sum(r['fields'].values()) for r in subset)/max(1,sum(len(r['fields']) for r in subset))}
    latencies=sorted(r['duration_ms'] for r in results)
    report={'available':True,'generated_at':datetime.now(timezone.utc).isoformat(),'scope':'Controlled regression corpus plus three public fictional upstream test documents. Variants share templates and are not independent real-world samples. No claim of universal invoice accuracy. Ground truth is authored before execution.','total':n,'external_count':sum(r['group']=='external' for r in results),'synthetic_count':sum(r['group']=='synthetic' for r in results),'decision_accuracy':sum(r['expected']==r['actual'] for r in results)/n,'false_approve_rate':false_approves/safe if safe else None,'false_approve_count':false_approves,'unsafe_input_count':safe,'straight_through_rate':sum(r['actual']=='APPROVED' for r in results)/n,'confusion_matrix':matrix,'routing':routing,'fields':fields,'latency_ms':{'p50':statistics.median(latencies),'p95':latencies[min(n-1,int(n*.95))]},'slices':{g:slice_report(g) for g in ['synthetic','external']},'modes':{},'failures':[r for r in results if r['expected']!=r['actual']],'results':results}
    for mode in ['ocr','text']:
        subset=[r for r in results if r['mode']==mode];conf=[r['ocr_confidence'] for r in subset if r['ocr_confidence'] is not None]
        report['modes'][mode]={'count':len(subset),'decision_accuracy':sum(r['actual']==r['expected'] for r in subset)/len(subset) if subset else None,'mean_ocr_confidence':statistics.mean(conf) if conf else None,'field_accuracy':sum(sum(r['fields'].values()) for r in subset)/max(1,sum(len(r['fields']) for r in subset))}
    report['scope']='350-file hard regression corpus: 100 public CORD receipt photographs with upstream human annotations, three public invoice fixtures, and independently specified synthetic/layout/degradation cases. Correlated variants are not independent real-world samples. Unreadable fields and held-out layouts remain limitations.'
    report['worst_failures']=sorted([r for r in results if r['field_misses'] or r['actual']!=r['expected']],key=lambda r:(r['actual']=='APPROVED' and r['expected']!='APPROVED',r['actual']!=r['expected'],len(r['field_misses'])),reverse=True)[:10]
    report['field_accuracy']=sum(v['correct'] for v in fields.values())/max(1,sum(v['total'] for v in fields.values()))
    out=ROOT/'reports';out.mkdir(exist_ok=True);(out/(output+'.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
    table=''.join('<tr>'+''.join('<td>'+html.escape(str(r[k]))+'</td>' for k in ['file','expected','actual','duration_ms','reason'])+'</tr>' for r in results)
    (out/(output+'.html')).write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>Vellum evaluation</title><style>body{font:16px system-ui;margin:40px;color:#222}table{border-collapse:collapse}td,th{border:1px solid #ddd;padding:10px}pre{white-space:pre-wrap}</style><h1>Vellum evaluation</h1><p>'+html.escape(report['scope'])+'</p><pre>'+html.escape(json.dumps({k:v for k,v in report.items() if k not in ['results','failures']},indent=2))+'</pre><table><tr><th>File</th><th>Expected</th><th>Actual</th><th>ms</th><th>Reason</th></tr>'+table+'</table></html>',encoding='utf-8')
    print(json.dumps({k:report[k] for k in ['total','decision_accuracy','false_approve_rate','straight_through_rate','slices']},indent=2),flush=True)
    return report
if __name__=='__main__':
    report=evaluate(next((a for a in sys.argv[1:] if not a.startswith('--')),'evaluation'))
    if '--require-zero-false-approves' in sys.argv and report['false_approve_count']:sys.exit(1)
