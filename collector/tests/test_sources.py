import datetime as dt
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from additional_sources import SOURCES, enabled, next_due, parse_feed
from server import Store, jobs

class SourceTests(unittest.TestCase):
    def test_no_unreviewed_source_can_run(self):
        for key in ['nowphas','kaiho','copernicus','nomads','jcope','jodc']:
            self.assertFalse(enabled(key))
        for key,source in SOURCES.items():
            if enabled(key):
                self.assertEqual(source['legal_review'],'approved_with_conditions')
                self.assertTrue(source['terms_urls'])
                self.assertTrue(source['attribution'])
                self.assertGreaterEqual(source['collection_interval_seconds'],60)

    def test_each_dataset_has_its_own_schedule(self):
        self.assertEqual(SOURCES['weather']['collection_interval_seconds'],1800)
        self.assertEqual(SOURCES['marine']['collection_interval_seconds'],3600)
        now=dt.datetime(2026,11,7,0,12,tzinfo=dt.timezone.utc).timestamp()
        jma=dt.datetime.fromtimestamp(next_due('jma-marine-bulletins',now),dt.timezone.utc)
        self.assertEqual((jma.hour,jma.minute),(1,10))
        noaa=dt.datetime.fromtimestamp(next_due('sst-analysis',now),dt.timezone.utc)
        self.assertEqual((noaa.hour,noaa.minute),(18,0))

    def test_feed_preserves_text_and_does_not_claim_active_warnings(self):
        now=dt.datetime.now(dt.timezone.utc).isoformat()
        raw=f'''<feed xmlns="http://www.w3.org/2005/Atom"><updated>{now}</updated>
        <entry><title>海上予想図</title><id>id</id><updated>{now}</updated><content>原文の概要</content><link href="https://www.data.jma.go.jp/developer/xml/data/x.xml"/></entry>
        <entry><title>陸上</title><updated>{now}</updated></entry></feed>'''.encode()
        data=parse_feed(raw,'jma-marine-bulletins')
        self.assertEqual(data['items'][0]['summary'],'原文の概要')
        self.assertEqual(len(data['items']),1)
        self.assertIn('NOT',data['scope'])
        with self.assertRaises(ValueError):parse_feed(b'<!DOCTYPE foo>'+raw,'jma-marine-bulletins')

    def test_schedule_survives_restart_and_backoff_isolated_per_dataset(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'db';store=Store(path)
            store.collect('weather','tokyo',lambda *_:{'current':{}})
            self.assertNotIn(('weather','tokyo'),Store(path).due_jobs())
            self.assertIn(('marine','tokyo'),Store(path).due_jobs())
            def fail(*_):raise TimeoutError()
            store.collect('marine','tokyo',fail)
            first=store.timing('marine','tokyo')
            store.collect('marine','tokyo',fail)
            second=store.timing('marine','tokyo')
            self.assertEqual(second['consecutive_failures'],2)
            self.assertGreater(second['next_attempt_at'],first['next_attempt_at'])
            with patch('server.fetch') as fetch:
                self.assertFalse(store.collect('nowphas','tokyo',fetch));fetch.assert_not_called()

    def test_custom_area_persistence_and_independent_jobs(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'db';store=Store(path)
            key,area=store.add_area({'name':'試験海域','bounds':{'south':34,'north':35,'west':139,'east':140}})
            self.assertEqual((area['lat'],area['lon']),(34.5,139.5))
            self.assertIn(key,Store(path).areas())
            self.assertIn(('weather',key),store.due_jobs())
            self.assertNotIn(('jma-marine-bulletins',key),store.due_jobs())
            for bounds in [{'south':35,'north':34,'west':139,'east':140},{'south':34,'north':35,'west':float('nan'),'east':140}]:
                with self.assertRaises(ValueError):store.add_area({'name':'invalid','bounds':bounds})
            self.assertFalse(store.delete_area('tokyo'))
            self.assertTrue(store.delete_area(key))
            self.assertNotIn(key,store.areas())

class WindowTests(unittest.TestCase):
    def test_history_forecast_boundaries_and_missing_data(self):
        from server import time_window
        now=dt.datetime(2026,11,7,0,30,tzinfo=dt.timezone(dt.timedelta(hours=9)))
        start=now.replace(hour=0,minute=0)-dt.timedelta(days=1)
        times=[(start+dt.timedelta(hours=i)).isoformat()[:16] for i in range(96)]
        data={'hourly':{'time':times,'wave_height':list(range(96))}}
        for window,count in [('history',12),('24',24),('36',36)]:
            result=time_window(data,window,now)
            self.assertEqual(len(result['hourly']['time']),count)
            self.assertEqual(len(result['hourly']['wave_height']),count)
            self.assertEqual(result['_window']['data_type'],'model_estimate_not_observation')
        self.assertEqual(len(data['hourly']['time']),96)
