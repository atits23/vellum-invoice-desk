import {z} from 'zod';
import crypto from 'node:crypto';
import {audit,hashPassword,password,email} from './auth.mjs';
const note=z.string().trim().min(5).max(2000),roles=z.enum(['Uploader','Reviewer','Admin']);
const csvCell=v=>'"'+String(v??'').replace(/^[=+@\-\t\r]/,"'$&").replaceAll('"','""')+'"';
export function registerAccess({app,db,requireUser,requireRole,upstream,env}){
 app.get('/api/admin/audit',requireUser,requireRole('Admin'),async(req,res)=>res.json(await db.prepare('SELECT a.*,u.name actor_name FROM security_audit a LEFT JOIN users u ON u.id=a.actor ORDER BY a.id DESC LIMIT 500').all()));
 app.post('/api/admin/users/create',requireUser,requireRole('Admin'),async(req,res)=>{
  const input=z.object({name:z.string().trim().min(2).max(100),email,password,role:roles,note}).parse(req.body);
  const id=crypto.randomUUID(),hash=await hashPassword(input.password);
  await db.transaction(async()=>{await db.prepare('INSERT INTO users(id,email,name,password_hash,role,verified) VALUES(?,?,?,?,?,1)').run(id,input.email,input.name,hash,input.role);await db.prepare('INSERT INTO user_controls(user_id,must_change_password) VALUES(?,1)').run(id);await audit(db,req.session.user_id,'user_created',{target:id,after:{name:input.name,email:input.email,role:input.role},note:input.note,verification:'Administrator provisioned; password change required'});})();res.status(201).json({message:'Account created. A password change is required on first sign-in.',id});
 });
 app.post('/api/admin/users/:id/state',requireUser,requireRole('Admin'),async(req,res)=>{
  const input=z.object({disabled:z.boolean(),note}).parse(req.body);const user=await db.prepare('SELECT * FROM users WHERE id=?').get(req.params.id);
  if(!user)return res.status(404).json({error:'User not found.'});
  if(env.DEMO_MODE==='true'&&(await db.prepare('SELECT is_demo FROM user_controls WHERE user_id=?').get(user.id))?.is_demo)return res.status(403).json({error:'Shared demo accounts are protected.'});
  if(user.id===req.session.user_id||user.email===env.BOOTSTRAP_ADMIN)return res.status(400).json({error:'The workspace owner and current administrator cannot be disabled.'});
  await db.transaction(async()=>{const before=await db.prepare('SELECT disabled FROM user_controls WHERE user_id=?').get(user.id);await db.prepare('INSERT OR IGNORE INTO user_controls(user_id) VALUES(?)').run(user.id);await db.prepare('UPDATE user_controls SET disabled=? WHERE user_id=?').run(Number(input.disabled),user.id);if(input.disabled)await db.prepare('DELETE FROM sessions WHERE user_id=?').run(user.id);await audit(db,req.session.user_id,'user_state_changed',{target:user.id,before:before?.disabled||0,after:Number(input.disabled),note:input.note});})();res.json({message:input.disabled?'User disabled and sessions revoked.':'User enabled.'});
 });
 app.get('/api/submissions',requireUser,async(req,res)=>{
  const response=await upstream('/api/runs');if(!response.ok)return res.status(503).json({error:'Invoice service unavailable.'});let rows=await response.json();
  const owners=await db.prepare('SELECT o.run_id,o.user_id,u.name,u.email FROM run_owners o LEFT JOIN users u ON u.id=o.user_id').all(),ownerMap=new Map(owners.map(o=>[o.run_id,o]));
  const assignments=new Map((await db.prepare('SELECT a.*,u.name reviewer_name FROM run_assignments a LEFT JOIN users u ON u.id=a.reviewer_id').all()).map(a=>[a.run_id,a]));
  if(req.session.role==='Uploader')rows=rows.filter(r=>ownerMap.get(r.id)?.user_id===req.session.user_id);
  rows=rows.map(r=>({...r,fields:JSON.parse(r.fields),decision:JSON.parse(r.decision),metadata:JSON.parse(r.metadata||'{}'),uploader:ownerMap.get(r.id)?.name||'Deleted account',uploader_id:ownerMap.get(r.id)?.user_id,assignment:assignments.get(r.id)||null}));
  const q=String(req.query.q||'').toLowerCase();
  rows=rows.filter(r=>(!q||[r.filename,r.fields.vendor,r.fields.invoice_number,r.uploader].join(' ').toLowerCase().includes(q))&&(!req.query.status||req.query.status==='ALL'||r.status===req.query.status)&&(!req.query.vendor||String(r.fields.vendor||'').toLowerCase().includes(String(req.query.vendor).toLowerCase()))&&(!req.query.uploader||r.uploader_id===req.query.uploader)&&(!req.query.from||r.created_at.slice(0,10)>=req.query.from)&&(!req.query.to||r.created_at.slice(0,10)<=req.query.to)&&(!req.query.confidence||req.query.confidence==='all'||(req.query.confidence==='text'?r.metadata.ocr_confidence==null:req.query.confidence==='low'?r.metadata.ocr_confidence!=null&&r.metadata.ocr_confidence<.85:r.metadata.ocr_confidence>=.85)));
  const sort=['created_at','status','uploader','filename'].includes(req.query.sort)?req.query.sort:'created_at',direction=req.query.direction==='asc'?1:-1;rows.sort((a,b)=>String(a[sort]||'').localeCompare(String(b[sort]||''))*direction);
  if(req.query.export==='csv'){res.type('text/csv').attachment('submissions.csv');return res.send([['Run','File','Status','Vendor','Uploader','Received','OCR confidence','Assigned reviewer'],...rows.map(r=>[r.id,r.filename,r.status,r.fields.vendor,r.uploader,r.created_at,r.metadata.ocr_confidence,r.assignment?.reviewer_name])].map(row=>row.map(csvCell).join(',')).join('\n'));}
  const page=Math.max(1,parseInt(req.query.page)||1),size=Math.min(100,Math.max(5,parseInt(req.query.size)||20));res.json({rows:rows.slice((page-1)*size,page*size),total:rows.length,page,size,pages:Math.max(1,Math.ceil(rows.length/size))});
 });
 app.post('/api/submissions/:id/assign',requireUser,requireRole('Admin'),async(req,res)=>{
  const input=z.object({reviewer_id:z.string().uuid(),note}).parse(req.body),reviewer=await db.prepare("SELECT u.id FROM users u LEFT JOIN user_controls c ON c.user_id=u.id WHERE u.id=? AND u.role IN ('Admin','Reviewer') AND COALESCE(c.disabled,0)=0").get(input.reviewer_id);
  if(!reviewer||!(/^[a-f0-9]{32}$/.test(req.params.id)))return res.status(400).json({error:'Choose an enabled reviewer and valid run.'});
  if(!(await upstream('/api/runs/'+req.params.id)).ok)return res.status(404).json({error:'Run not found.'});
  await db.transaction(async()=>{const before=await db.prepare('SELECT * FROM run_assignments WHERE run_id=?').get(req.params.id);await db.prepare('DELETE FROM run_assignments WHERE run_id=?').run(req.params.id);await db.prepare('INSERT INTO run_assignments(run_id,reviewer_id,assigned_by,note) VALUES(?,?,?,?)').run(req.params.id,input.reviewer_id,req.session.user_id,input.note);await audit(db,req.session.user_id,'run_assigned',{run:req.params.id,before,after:input});})();res.json({message:'Reviewer assigned; audit recorded.'});
 });
 app.post('/api/submissions/:id/override',requireUser,requireRole('Admin'),async(req,res)=>{
  const input=z.object({status:z.enum(['APPROVED','REVIEW','REJECTED']),note}).parse(req.body);if(!/^[a-f0-9]{32}$/.test(req.params.id))return res.status(404).json({error:'Run not found.'});
  const response=await upstream('/api/runs/'+req.params.id+'/override',{method:'POST',headers:{'Content-Type':'application/json','X-Actor':req.session.user_id},body:JSON.stringify(input)});res.status(response.status).json(await response.json());
 });
}
