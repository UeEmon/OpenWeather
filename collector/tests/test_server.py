import copy
import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
from http.server import ThreadingHTTPServer
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Store, AREAS, PROVIDERS, make_handler, validate, upstream_url


def fixture(kind):
    params = PROVIDERS[kind][1]
    stamp = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).isoformat(timespec='minutes')[:16]
    data = {}
    for group in ['current', 'hourly'] + (['daily'] if kind == 'weather' else []):
        n = 24 if group == 'hourly' else 7
        data[group] = {'time': stamp if group == 'current' else [stamp] * n}
        for key in params[group].split(','):
            data[group][key] = 1.2 if group == 'current' else [1.2] * n
    return data


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'data.sqlite3'
        self.store = Store(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_failure_keeps_good_snapshot_and_restart_restores(self):
        self.assertTrue(self.store.collect('marine', 'tokyo', lambda *_: fixture('marine')))
        def fail(*_): raise TimeoutError('sensitive URL not to be exposed')
        self.assertFalse(self.store.collect('marine', 'tokyo', fail))
        data = Store(self.path).read('marine', 'tokyo')
        self.assertEqual(data['current']['wave_height'], 1.2)
        self.assertTrue(data['_meta']['last_collection_failed'])
        self.assertNotIn('sensitive', json.dumps(data))
        with self.store.connect() as db:
            db.execute('UPDATE snapshots SET fetched=?', (time.time()-7200,))
        self.assertTrue(self.store.read('marine','tokyo')['_meta']['stale'])

    def test_validation_rejects_bad_arrays_old_data_and_null_current(self):
        for kind in PROVIDERS:
            good = fixture(kind)
            self.assertIs(validate(kind,good), good)
            for change in ['array','current','time']:
                bad = copy.deepcopy(good)
                if change == 'array': bad['hourly']['time'] = []
                if change == 'current': bad['current'][('wave_height' if kind=='marine' else 'temperature_2m')] = None
                if change == 'time': bad['current']['time'] = '2000-01-01T00:00'
                with self.assertRaises(ValueError): validate(kind,bad)

    def test_provider_parameters(self):
        self.assertIn('wind_speed_unit=ms',upstream_url('weather',AREAS['tokyo']))
        self.assertIn('forecast_days=3',upstream_url('marine',AREAS['tokyo']))

    def test_api_contract_and_no_request_time_fetch(self):
        http = ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.store))
        thread = threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        base = f'http://127.0.0.1:{http.server_port}'
        def get(path):
            try:
                with urllib.request.urlopen(base+path) as r:return r.status,json.load(r)
            except urllib.error.HTTPError as e:return e.code,json.load(e)
        try:
            self.assertEqual(get('/health')[0],200)
            self.assertEqual(get('/ready')[0],503)
            self.assertEqual(len(get('/api/v1/areas')[1]),8)
            self.assertEqual(get('/api/v1/marine?area=tokyo')[0],503)
            self.assertEqual(get('/api/v1/marine?area=invalid')[0],400)
            self.assertEqual(get('/api/v1/marine?area=tokyo&url=http://evil')[0],400)
            self.assertEqual(get('/api/v1/marine?area=tokyo&area=naha')[0],400)
            self.assertEqual(get('/unknown')[0],404)
            for kind in PROVIDERS:
                for area in AREAS:self.store.collect(kind,area,lambda k,_:fixture(k))
            with patch('server.fetch',side_effect=AssertionError('read must not fetch')):
                code,data=get('/api/v1/marine?area=tokyo')
                self.assertEqual(code,200)
                self.assertFalse(data['_meta']['stale'])
                self.assertEqual(get('/ready')[0],200)
                self.assertTrue(get('/api/v1/status')[1]['ready'])
        finally:
            http.shutdown();http.server_close();thread.join()

if __name__=='__main__':unittest.main()
