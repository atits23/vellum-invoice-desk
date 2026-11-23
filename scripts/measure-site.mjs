import {spawn} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import {chromium} from '@playwright/test';
import lighthouse from 'lighthouse';
import {launch} from 'chrome-launcher';

const directory=path.resolve('tmp/lighthouse-'+Date.now());fs.mkdirSync(directory,{recursive:true});
const log=fs.openSync(path.join(directory,'server.log'),'a');
const server=spawn(process.execPath,['web/server.mjs'],{env:{...process.env,DATABASE_URL:'',BREVO_API_KEY:'',SMTP_URL:'',PORT:'8020',ENGINE_PORT:'9020',PUBLIC_URL:'http://localhost:8020',DATA_DIR:directory,NODE_ENV:'test'},stdio:['ignore',log,log],windowsHide:true});
let chrome;
try{
 for(let n=0;n<100;n++){try{if((await fetch('http://localhost:8020/health')).ok)break;}catch{}await new Promise(r=>setTimeout(r,250));}
 chrome=await launch({chromePath:chromium.executablePath(),chromeFlags:['--headless','--no-sandbox']});
 const result=await lighthouse('http://localhost:8020',{port:chrome.port,output:['html','json'],logLevel:'error',onlyCategories:['performance','accessibility','best-practices','seo']});
 fs.writeFileSync('reports/lighthouse.html',result.report[0]);fs.writeFileSync('reports/lighthouse.json',result.report[1]);
 console.log(JSON.stringify(Object.fromEntries(Object.entries(result.lhr.categories).map(([k,v])=>[k,v.score*100]))));
 console.log(JSON.stringify(Object.values(result.lhr.audits).filter(a=>a.score!==null&&a.score<1).map(a=>({id:a.id,score:a.score,title:a.title,description:a.description})),null,2));
}finally{if(chrome)await chrome.kill();server.kill();}
