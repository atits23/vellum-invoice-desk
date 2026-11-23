import {openAuth,hashPassword,random} from '../web/auth.mjs';
import crypto from 'node:crypto';
const db=await openAuth(process.env.DATA_DIR||'data');
const email=process.env.DEMO_EMAIL||'demo@vellum.example';
const password=process.env.DEMO_PASSWORD||random().slice(0,24);
if(await db.prepare('SELECT 1 FROM users WHERE email=?').get(email)){console.log('Demo account already exists; no credentials changed.');await db.close();process.exit(0);}
if(password.length<12)throw Error('Demo password must be at least 12 characters');
await db.prepare('INSERT INTO users(id,email,name,password_hash,verified,role) VALUES(?,?,?,?,1,?)').run(crypto.randomUUID(),email,'Demo reviewer',await hashPassword(password),'Reviewer');
console.log('Demo reviewer created. Use only fictional invoices in the demo workspace.');
console.log('Email: '+email);console.log('Password: '+password);await db.close();
