import {spawn} from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
const dir=path.resolve('tmp/e2e-'+Date.now());fs.mkdirSync(dir,{recursive:true});fs.writeFileSync('tmp/e2e-directory.txt',dir);
const log=fs.openSync(path.join(dir,'server.log'),'a');
const child=spawn(process.execPath,['web/server.mjs'],{env:{...process.env,DATABASE_URL:'',BREVO_API_KEY:'',SMTP_URL:'',PORT:'8010',PUBLIC_URL:'http://localhost:8010',DATA_DIR:dir,ENGINE_PORT:'9010',NODE_ENV:'test',DEMO_MODE:'true',BOOTSTRAP_ADMIN:'e2e@example.com'},stdio:['ignore',log,log],windowsHide:true});
child.on('exit',code=>process.exit(code||0));for(const s of ['SIGINT','SIGTERM'])process.on(s,()=>child.kill());
