import Database from 'better-sqlite3';
import pg from 'pg';
pg.types.setTypeParser(20,value=>Number(value));
import {AsyncLocalStorage} from 'node:async_hooks';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

// One asynchronous interface for local SQLite and hosted PostgreSQL.
export async function database(directory,url){
 fs.mkdirSync(directory,{recursive:true});
 const context=new AsyncLocalStorage();let tail=Promise.resolve();
 const sqlite=url?null:new Database(path.join(directory,'accounts.sqlite3'));
 const schema=process.env.DB_SCHEMA||'accounts_'+crypto.createHash('sha256').update(path.resolve(directory)).digest('hex').slice(0,12);
 if(!/^[a-z][a-z0-9_]{0,60}$/.test(schema))throw Error('Invalid DB_SCHEMA');
 const pool=url?new pg.Pool({connectionString:url,max:5,connectionTimeoutMillis:15000}):null;
 if(pool)await pool.query(`CREATE SCHEMA IF NOT EXISTS ${schema}`);
 else{sqlite.pragma('journal_mode=WAL');sqlite.pragma('foreign_keys=ON');sqlite.pragma('busy_timeout=10000');}
 const translate=sql=>{let index=0;return sql.replace(/\?/g,()=>'$'+(++index)).replace(/INTEGER PRIMARY KEY AUTOINCREMENT/g,'BIGSERIAL PRIMARY KEY').replace(/\bexpires INTEGER/g,'expires BIGINT').replace(/\bcreated INTEGER/g,'created BIGINT').replace(/TEXT DEFAULT CURRENT_TIMESTAMP/g,'TEXT DEFAULT (CURRENT_TIMESTAMP::text)').replace(/INSERT OR IGNORE INTO ([\s\S]*)/g,'INSERT INTO $1 ON CONFLICT DO NOTHING');};
 async function locked(fn){if(context.getStore())return fn();let release;const previous=tail;tail=new Promise(r=>release=r);await previous;try{return await fn();}finally{release();}}
 async function query(sql,params=[],kind='all'){
  if(pool){
   const active=context.getStore()?.client,client=active||await pool.connect();
   try{if(!active){await client.query('BEGIN');await client.query(`SET LOCAL search_path TO ${schema}`);}const result=await client.query(translate(sql),params);if(!active)await client.query('COMMIT');return kind==='get'?result.rows[0]:kind==='run'?{changes:result.rowCount}:result.rows;}
   catch(error){if(!active)await client.query('ROLLBACK');throw error;}finally{if(!active)client.release();}
  }
  return locked(()=>sqlite.prepare(sql.replace(/ FOR UPDATE/g,''))[kind](...params));
 }
 return {prepare(sql){return {get:(...params)=>query(sql,params,'get'),all:(...params)=>query(sql,params,'all'),run:(...params)=>query(sql,params,'run')};},
  async exec(sql){if(pool){for(const statement of sql.split(';').filter(s=>s.trim()))await query(statement);}else await locked(()=>sqlite.exec(sql));},
  transaction(fn){return async(...args)=>{
   if(pool){const client=await pool.connect();try{await client.query('BEGIN');await client.query(`SET LOCAL search_path TO ${schema}`);const result=await context.run({client},()=>fn(...args));await client.query('COMMIT');return result;}catch(e){await client.query('ROLLBACK');throw e;}finally{client.release();}}
   return locked(()=>context.run({transaction:true},async()=>{sqlite.exec('BEGIN IMMEDIATE');try{const result=await fn(...args);sqlite.exec('COMMIT');return result;}catch(e){sqlite.exec('ROLLBACK');throw e;}}));
  };},
  async close(){if(pool)await pool.end();else sqlite.close();}
 };
}
