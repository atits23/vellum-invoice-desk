import json
import os
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from unittest.mock import patch
from app.server import make_server

class HttpIntegration(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.token='a-test-token-with-at-least-24-characters'
        with patch.dict(os.environ,{'APP_TOKEN':self.token}):
            self.server=make_server(port=0,data_dir=self.temp.name)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base='http://127.0.0.1:'+str(self.server.server_address[1])
    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join();self.server.service.stop();self.temp.cleanup()
    def request(self,path,body=None,auth=True,headers=None):
        h={'Authorization':'Bearer '+self.token} if auth else {}
        h.update(headers or {})
        return urllib.request.urlopen(urllib.request.Request(self.base+path,data=body,headers=h),timeout=10)
    def test_authentication_and_static_ui(self):
        with self.request('/') as response:self.assertIn(b'Vellum',response.read())
        with self.assertRaises(urllib.error.HTTPError) as context:self.request('/api/runs',auth=False)
        self.assertEqual(context.exception.code,401)
        with self.request('/health',auth=False) as response:self.assertEqual(json.load(response)['status'],'ok')
    def test_upload_review_and_exports(self):
        source=(Path(__file__).resolve().parent.parent/'samples/04-ambiguous-po.pdf').read_bytes()
        with self.request('/api/runs',source,headers={'X-Filename':'test.pdf','Content-Type':'application/pdf'}) as response:rid=json.load(response)['id']
        self.server.service.queue.join()
        with self.request('/api/runs/'+rid) as response:run=json.load(response)
        self.assertEqual(run['status'],'REVIEW')
        run['fields']['po_number']='PO-2001'
        payload=json.dumps({'fields':run['fields'],'note':'Buyer confirmed PO reference','verified':True}).encode()
        with self.request('/api/runs/'+rid+'/review',payload) as response:self.assertEqual(json.load(response)['status'],'APPROVED')
        with self.request('/api/runs/'+rid+'/source') as response:self.assertEqual(response.read(),source)
        with self.request('/api/runs/'+rid+'/export') as response:self.assertEqual(json.load(response)['status'],'APPROVED')
        with self.request('/api/export.csv') as response:self.assertIn(b'APPROVED',response.read())

if __name__=='__main__':unittest.main()
