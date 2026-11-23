import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';
import path from 'node:path';

test('signup, verify, login, upload, stream decision, review, dashboard and logout',async({page})=>{
 await page.goto('/app');await expect(page).toHaveURL(/\/login\?callbackUrl/);
 await page.goto('/signup');await page.getByLabel('Full name').fill('Evaluation Reviewer');await page.getByLabel('Email',{exact:true}).fill('e2e@example.com');await page.getByLabel('Password (12+ characters)',{exact:true}).fill('test-password-strong-2468');await page.getByRole('button',{name:'Create account'}).click();await expect(page.locator('.form-status')).toContainText('verification link');
 const dir=fs.readFileSync('tmp/e2e-directory.txt','utf8');const mail=fs.readFileSync(path.join(dir,'server.log'),'utf8').split('\n').filter(l=>l.includes('development_mail')).map(l=>JSON.parse(l)).find(l=>l.email==='e2e@example.com');
 await page.goto(mail.link);await page.getByRole('button',{name:'Verify email'}).click();await expect(page.locator('.form-status')).toContainText('Email verified');
 await page.goto('/login');await page.getByLabel('Email',{exact:true}).fill('e2e@example.com');await page.getByLabel('Password',{exact:true}).fill('test-password-strong-2468');await page.getByRole('button',{name:'Sign in',exact:true}).click();await expect(page).toHaveURL('/app');
 await page.locator('#upload').setInputFiles('samples/01-happy-path.pdf');await expect(page.locator('.decision-banner')).toContainText('Approved',{timeout:30000});await expect(page.locator('.timeline')).toContainText('rules_checked');await page.getByRole('button',{name:'Close invoice'}).click();
 await page.locator('#upload').setInputFiles('samples/02-split-over-budget.pdf');await expect(page.locator('.decision-banner')).toContainText('Needs review',{timeout:30000});await expect(page.locator('.rule').filter({hasText:'budget'})).toContainText('420.00');await page.getByRole('button',{name:'Close invoice'}).click();
 await page.locator('#upload').setInputFiles('samples/03-semantic-duplicate.pdf');await expect(page.locator('.decision-banner')).toContainText('Rejected',{timeout:30000});await page.getByRole('button',{name:'Close invoice'}).click();
 await page.locator('#upload').setInputFiles('samples/04-ambiguous-po.pdf');await expect(page.locator('.decision-banner')).toContainText('Needs review',{timeout:30000});await page.locator('input[name=po_number]').fill('PO-2001');await page.locator('input[name=note]').fill('Buyer confirmed PO-2001 against original purchase order.');await page.locator('input[name=verified]').check();await page.getByRole('button',{name:'Revalidate & decide'}).click();await expect(page.locator('.decision-banner')).toContainText('Approved');await page.getByRole('button',{name:'Close invoice'}).click();
 await page.locator('#upload').setInputFiles('samples/09-scanned-invoice.pdf');await expect(page.locator('.decision-banner')).toContainText('Needs review',{timeout:30000});await expect(page.locator('.source-preview')).toContainText('OCR confidence');await page.locator('input[name=note]').fill('Verified scan against the original document and confirmed separate delivery.');await page.locator('input[name=verified]').check();await page.getByRole('button',{name:'Revalidate & decide'}).click();await expect(page.locator('.decision-banner')).toContainText('Approved');await page.getByRole('button',{name:'Close invoice'}).click();await expect(page.locator('#run-count')).toHaveText('5');const appA11y=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();expect(appA11y.violations).toEqual([]);await page.screenshot({path:'docs/workspace-v2.png',fullPage:true});
 await page.getByRole('button',{name:'Log out',exact:true}).click();await expect(page).toHaveURL(/loggedOut=1/);await expect(page.locator('#toast')).toContainText('logged out');await page.goto('/app');await expect(page).toHaveURL(/\/login\?callbackUrl/);
});

for(const width of [360,768,1024,1440])test(`marketing responsive and accessibility ${width}`,async({page})=>{
 await page.setViewportSize({width,height:1000});await page.goto('/');await expect(page.getByRole('heading',{level:1})).toContainText('Hand off the invoice');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
 const results=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();expect(results.violations).toEqual([]);
 await page.screenshot({path:`docs/marketing-${width}.png`,fullPage:true});
});
