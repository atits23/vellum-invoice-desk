"""PostgreSQL implementation of the small DB-API surface used by the rule engine."""
import re
from pathlib import Path
import sys
deps=Path(__file__).resolve().parent.parent/'.deps'
if deps.exists():sys.path.insert(0,str(deps))

class Record(dict):
    def __getitem__(self,key):return list(self.values())[key] if isinstance(key,int) else super().__getitem__(key)

class Result:
    def __init__(self,cursor=None,rows=None):self.cursor=cursor;self.rows=rows
    def fetchone(self):
        value=self.rows.pop(0) if self.rows else self.cursor.fetchone() if self.cursor else None
        return Record(value) if value is not None else None
    def __iter__(self):
        rows=self.rows if self.rows is not None else self.cursor.fetchall()
        return iter(Record(r) for r in rows)

class Connection:
    def __init__(self,url,schema):
        import psycopg
        from psycopg.rows import dict_row
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,60}',schema):raise ValueError('Invalid database schema')
        self.db=psycopg.connect(url,row_factory=dict_row,connect_timeout=15)
        self.db.execute('CREATE SCHEMA IF NOT EXISTS '+schema)
        self.db.commit()
        self.schema=schema
    def execute(self,sql,params=()):
        from psycopg.pq import TransactionStatus
        if self.db.info.transaction_status==TransactionStatus.IDLE:
            self.db.execute('SET LOCAL search_path TO '+self.schema)
        if sql.strip().startswith('PRAGMA table_info('):
            table=sql.split('(')[1].rstrip(')')
            cur=self.db.execute('SELECT ordinal_position AS cid,column_name AS name FROM information_schema.columns WHERE table_schema=%s AND table_name=%s ORDER BY ordinal_position',(self.schema,table))
            return Result(cur)
        if sql.strip().startswith('PRAGMA'):return Result(rows=[])
        if sql=='BEGIN IMMEDIATE':
            # One transaction-scoped workspace lock serializes reservation and duplicate checks.
            return Result(self.db.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",(self.schema,)))
        sql=sql.replace('?','%s').replace('INTEGER PRIMARY KEY AUTOINCREMENT','BIGSERIAL PRIMARY KEY')
        sql=re.sub(r'\b(amount_minor|reserved_minor) INTEGER',r'\1 BIGINT',sql)
        if sql.startswith('INSERT OR IGNORE'):
            sql=sql.replace('INSERT OR IGNORE','INSERT',1)+' ON CONFLICT DO NOTHING'
        return Result(self.db.execute(sql,params))
    def executemany(self,sql,rows):
        for row in rows:self.execute(sql,row)
    def executescript(self,script):
        for statement in script.split(';'):
            if statement.strip():self.execute(statement.strip())
    def __enter__(self):return self
    def __exit__(self,kind,value,trace):
        try:self.db.rollback() if kind else self.db.commit()
        finally:self.db.close()
