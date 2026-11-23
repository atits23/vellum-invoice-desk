import os,sys,tempfile,uuid,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent;sys.path.insert(0,str(ROOT))
from app.store import Store
from app.service import Service
from app.postgres import Connection

url=os.environ['DATABASE_URL'];schema='test_vellum_'+uuid.uuid4().hex
try:
    with tempfile.TemporaryDirectory() as folder:
        store=Store(folder,url,schema);service=Service(store,start_worker=False)
        source=(ROOT/'samples/01-happy-path.pdf').read_bytes();rid=service.submit(source,'sample.pdf');service.process(rid)
        assert store.get(rid)['status']=='APPROVED',store.get(rid)
        assert store.source(rid)==source
        # A new filesystem directory still retrieves the persisted original and decision.
        with tempfile.TemporaryDirectory() as other:
            restored=Store(other,url,schema)
            assert restored.get(rid)['status']=='APPROVED'
            assert restored.source(rid)==source
            duplicate=Service(restored,start_worker=False);other_id=duplicate.submit(source,'resent.pdf');duplicate.process(other_id)
            assert restored.get(other_id)['status']=='REJECTED'
        print('PostgreSQL: migrations, approval, source persistence, restart and duplicate checks passed.')
finally:
    with Connection(url,schema) as connection:connection.db.execute('DROP SCHEMA '+schema+' CASCADE')
