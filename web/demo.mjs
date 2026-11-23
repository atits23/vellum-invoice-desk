import crypto from 'node:crypto';
import {hashPassword,audit} from './auth.mjs';

export const demoAccounts=[['admin@vellum.example','Demo Admin','Admin','Vellum-Demo-Admin-2026!'],['reviewer@vellum.example','Demo Reviewer','Reviewer','Vellum-Demo-Review-2026!'],['uploader@vellum.example','Demo Uploader','Uploader','Vellum-Demo-Upload-2026!']];
export async function seedDemo(db,enabled){
 if(!enabled)return;
 for(const [email,name,role,password] of demoAccounts){
  if(await db.prepare('SELECT id FROM users WHERE email=?').get(email))continue;
  const id=crypto.randomUUID(),hash=await hashPassword(password);
  await db.transaction(async()=>{await db.prepare('INSERT INTO users(id,email,name,password_hash,role,verified) VALUES(?,?,?,?,?,1)').run(id,email,name,hash,role);await db.prepare('INSERT INTO user_controls(user_id,is_demo,must_change_password) VALUES(?,1,1)').run(id);await audit(db,id,'demo_account_seeded',{role,fictional:true});})();
 }
}
