import {chromium,expect} from '@playwright/test';
import fs from 'node:fs';
import {demoAccounts} from '../web/demo.mjs';
const base=process.env.LIVE_URL||'https://vellum-invoice-desk-atits23.onrender.com';
const browser=await chromium.launch();const results=[];let ownedRun;
fs.mkdirSync('docs/qa/live',{recursive:true});
try{
 for(const index of [2,1,0]){
  const [email,,role,password]=demoAccounts[index],context=await browser.newContext(),page=await context.newPage();page.setDefaultTimeout(90000);
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/login');await page.getByLabel('Email',{exact:true}).fill(email);await page.getByLabel('Password',{exact:true}).fill(password);await page.getByRole('button',{name:'Sign in',exact:true}).click();await expect(page).toHaveURL(base+'/app');await expect(page.locator('#dashboard .metric')).toHaveCount(6);
  const metrics=await(await page.request.get(base+'/api/metrics')).json();expect(metrics.total).toBe(350);expect(metrics.false_approve_count).toBe(0);
  const session=await(await page.request.get(base+'/auth/session')).json();const headers={'X-CSRF-Token':session.csrf,Origin:base};
  if(role==='Uploader'){
   await page.locator('[data-tab=invoices]').click();await page.locator('#upload').setInputFiles('tests/corpus/cord-test-0000.jpg');await expect(page.locator('.decision-banner')).toContainText(/Needs review|Rejected/,{timeout:120000});
   const rows=await(await page.request.get(base+'/api/submissions')).json();expect(rows.total).toBeGreaterThan(0);expect(rows.rows.every(r=>r.uploader_id===session.user.id)).toBe(true);ownedRun=rows.rows[0].id;
   await page.screenshot({path:'docs/qa/live/uploader-run.png',fullPage:true});await page.getByRole('button',{name:'Close invoice'}).click();expect((await page.request.get(base+'/api/admin/users')).status()).toBe(403);
  }else{
   const rows=await(await page.request.get(base+'/api/submissions')).json();expect(rows.rows.some(r=>r.id===ownedRun)).toBe(true);
   if(role==='Reviewer'){expect((await page.request.get(base+'/api/policy')).status()).toBe(403);expect((await page.request.get(base+'/api/admin/users')).status()).toBe(403);}
   else{const users=await(await page.request.get(base+'/api/admin/users')).json();const reviewer=users.find(u=>u.email===demoAccounts[1][0]);expect((await page.request.post(base+'/api/submissions/'+ownedRun+'/assign',{headers,data:{reviewer_id:reviewer.id,note:'Live verification: review this public receipt fixture.'}})).status()).toBe(200);}
  }
  await page.locator('[data-tab=dashboard]').click();await page.screenshot({path:`docs/qa/live/${role.toLowerCase()}.png`,fullPage:true});
  await page.locator('[data-tab=evaluation]').click();await expect(page.locator('#evaluation')).toContainText('Before and after');await expect(page.locator('#evaluation')).toContainText('Ten worst remaining failures');
  await page.getByRole('button',{name:'Log out',exact:true}).click();await expect(page).toHaveURL(/loggedOut=1/);await page.goto(base+'/app');await expect(page).toHaveURL(/login\?callbackUrl/);expect(errors).toEqual([]);
  results.push({role,login:true,report:true,permissions:true,logout:true,consoleErrors:errors});await context.close();
 }
 fs.writeFileSync('reports/live-roles.json',JSON.stringify({verified_at:new Date().toISOString(),url:base,results},null,2));console.log(JSON.stringify(results));
}finally{await browser.close();}
