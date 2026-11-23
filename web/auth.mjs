import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import {database} from './database.mjs';
import argon2 from 'argon2';
import {z} from 'zod';

export const password=z.string().min(12,'Use at least 12 characters.').max(128);
export const email=z.string().email().max(254).transform(v=>v.trim().toLowerCase());
export const signupSchema=z.object({name:z.string().trim().min(2).max(100),email,password}).strict();
export const loginSchema=z.object({email,password:z.string().min(1).max(128),remember:z.boolean().default(false)}).strict();
export const digest=value=>crypto.createHash('sha256').update(value).digest('hex');
export const random=()=>crypto.randomBytes(32).toString('hex');
export const safeUser=u=>u?{id:u.id,email:u.email,name:u.name,role:u.role,verified:!!u.verified}:null;
export const hashPassword=value=>argon2.hash(value,{type:argon2.argon2id,memoryCost:65536,timeCost:3,parallelism:1});
export async function openAuth(directory,url){const db=await database(directory,url);await db.exec(fs.readFileSync(new URL('./migrations/001_accounts.sql',import.meta.url),'utf8'));return db;}
export async function sessionFrom(db,req){const cookie=req.headers.cookie?.split(';').map(v=>v.trim()).find(v=>v.startsWith('vellum_session='))?.slice(15);if(!cookie||!/^[a-f0-9]{64}$/.test(cookie))return null;return await db.prepare('SELECT s.*,u.email,u.name,u.role,u.verified FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.id=? AND s.expires>?').get(digest(cookie),Date.now());}
export async function newSession(db,user,remember,agent){const raw=random(),csrf=random(),expires=Date.now()+(remember?30:1)*86400000;await db.prepare('INSERT INTO sessions VALUES(?,?,?,?,?,?)').run(digest(raw),user.id,csrf,expires,Date.now(),String(agent||'Unknown browser').slice(0,200));return {raw,csrf,expires};}
export async function issueToken(db,user,kind){const raw=random();await db.prepare('DELETE FROM tokens WHERE user_id=? AND kind=?').run(user.id,kind);await db.prepare('INSERT INTO tokens VALUES(?,?,?,?)').run(digest(raw),user.id,kind,Date.now()+(kind==='verify'?86400000:3600000));return raw;}
export async function consumeToken(db,raw,kind,callback){return await db.transaction(async()=>{const t=await db.prepare('SELECT * FROM tokens WHERE digest=? AND kind=? AND expires>? FOR UPDATE').get(digest(raw),kind,Date.now());if(!t)throw Error('This link is invalid or expired. Request a new one.');await callback(t.user_id);await db.prepare('DELETE FROM tokens WHERE digest=?').run(digest(raw));return t.user_id;})();}
export async function audit(db,actor,action,detail={}){await db.prepare('INSERT INTO security_audit(actor,action,detail) VALUES(?,?,?)').run(actor||null,action,JSON.stringify(detail));}
