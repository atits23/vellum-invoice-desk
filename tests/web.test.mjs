import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import {createApp} from '../web/server.mjs';
import {issueToken,hashPassword} from '../web/auth.mjs';

test('accounts: validation, verification, login, CSRF, protected routes, sessions, reset and logout',async t=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'vellum-auth-'));
 const {app,db}=await createApp({env:{NODE_ENV:'test',PUBLIC_URL:'http://localhost:8000',DATA_DIR:dir,BOOTSTRAP_ADMIN:'owner@example.com'},engineToken:'test-only'});
 const server=app.listen(0,'127.0.0.1');await new Promise(r=>server.once('listening',r));const base='http://127.0.0.1:'+server.address().port;let cookie='',csrf='';
 async function req(url,data,extra={}){const response=await fetch(base+url,{method:data===undefined?'GET':'POST',redirect:'manual',headers:{Origin:'http://localhost:8000','Content-Type':'application/json',Cookie:cookie,'X-CSRF-Token':csrf,...extra},body:data===undefined?undefined:JSON.stringify(data)});return response;}
 try{
  await t.test('protected page redirects',async()=>{const r=await req('/app/settings');assert.equal(r.status,302);assert.match(r.headers.get('location'),/callbackUrl/);});
  await t.test('signup rejects weak password',async()=>assert.equal((await req('/auth/signup',{name:'Owner',email:'owner@example.com',password:'short'})).status,400));
  await t.test('verification is required',async()=>{assert.equal((await req('/auth/signup',{name:'Owner',email:'owner@example.com',password:'correct-horse-battery-123'})).status,202);assert.equal((await req('/auth/login',{email:'owner@example.com',password:'correct-horse-battery-123'})).status,401);});
  await t.test('single-use email verification',async()=>{const user=await db.prepare('SELECT * FROM users WHERE email=?').get('owner@example.com');const token=await issueToken(db,user,'verify');assert.equal((await req('/auth/verify',{token})).status,200);assert.equal((await req('/auth/verify',{token})).status,400);});
  await t.test('login creates HttpOnly cookie and CSRF token',async()=>{const r=await req('/auth/login',{email:'owner@example.com',password:'correct-horse-battery-123',remember:true});assert.equal(r.status,200);assert.match(r.headers.get('set-cookie'),/HttpOnly/);assert.match(r.headers.get('set-cookie'),/SameSite=Lax/i);cookie=r.headers.get('set-cookie').split(';')[0];const data=await r.json();csrf=data.csrf;assert.equal(data.user.role,'Admin');assert.equal((await req('/login')).status,302);});
  await t.test('CSRF and origin enforcement',async()=>{assert.equal((await req('/api/settings/profile',{name:'New name'},{'X-CSRF-Token':''})).status,403);assert.equal((await req('/api/settings/profile',{name:'New name'},{Origin:'https://attacker.example'})).status,403);assert.equal((await req('/api/settings/profile',{name:'New name'})).status,200);});
  await t.test('settings list current session',async()=>{const r=await(await req('/api/settings')).json();assert.equal(r.sessions.length,1);assert.equal(r.sessions[0].current,true);});
  await t.test('logout revokes session',async()=>{assert.equal((await req('/auth/logout',{})).status,200);assert.equal((await req('/api/settings')).status,401);assert.equal((await req('/app')).status,302);cookie='';csrf='';});
  await t.test('password reset is single use',async()=>{const user=await db.prepare('SELECT * FROM users WHERE email=?').get('owner@example.com');const token=await issueToken(db,user,'reset');assert.equal((await req('/auth/reset',{token,password:'new-correct-password-123'})).status,200);assert.equal((await req('/auth/reset',{token,password:'new-correct-password-123'})).status,400);assert.equal((await req('/auth/login',{email:'owner@example.com',password:'correct-horse-battery-123'})).status,401);});
  await t.test('contact saved without pretending a booking',async()=>{const r=await req('/api/contact',{name:'Demo user',email:'demo@example.com',message:'Please show me the review workflow.'});assert.equal(r.status,201);assert.equal((await db.prepare('SELECT count(*) n FROM contacts').get()).n,1);});
  await t.test('production rejects missing mail configuration',async()=>{await assert.rejects(()=>createApp({env:{NODE_ENV:'production',PUBLIC_URL:'http://localhost:8000',DATA_DIR:dir},engineToken:'test'}));});
 }finally{await new Promise(r=>server.close(r));await db.close();fs.rmSync(dir,{recursive:true,force:true});}
});
