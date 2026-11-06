"""Shared marine/weather collector. HTTP readers never contact upstream services."""
import concurrent.futures
import datetime as dt
import json
import logging
import math
import os
from pathlib import Path
import signal
import sqlite3
import threading
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from additional_sources import SOURCES, GLOBAL_KINDS, enabled, interval, next_due, source_url, fetch_additional

AREAS = json.loads((Path(__file__).parent / 'areas.json').read_text())
PROVIDERS = {
    'weather': ('https://api.open-meteo.com/v1/forecast', {
        'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,weather_code,wind_speed_10m',
        'hourly': 'temperature_2m,precipitation_probability,weather_code,is_day',
        'daily': 'weather_code,temperature_2m_max,temperature_2m_min,sunset,precipitation_probability_max',
        'wind_speed_unit': 'ms', 'cell_selection': 'sea', 'past_hours': '12', 'forecast_days': '7'}),
    'marine': ('https://marine-api.open-meteo.com/v1/marine', {
        'current': 'wave_height,wave_direction,wave_period,sea_surface_temperature',
        'hourly': 'wave_height,wave_direction,wave_period', 'past_hours': '12', 'forecast_days': '3'})}


def upstream_url(kind, area):
    endpoint, params = PROVIDERS[kind]
    return endpoint + '?' + urllib.parse.urlencode(dict(params, latitude=area['lat'], longitude=area['lon'], timezone='Asia/Tokyo'))


def validate(kind, data):
    """Reject malformed/empty data without overwriting the last good snapshot."""
    if not isinstance(data, dict) or data.get('error'):
        raise ValueError('upstream error')
    groups = ['current', 'hourly'] + (['daily'] if kind == 'weather' else [])
    required = {name: params.split(',') for name, params in PROVIDERS[kind][1].items() if name in groups}
    for group in groups:
        block = data.get(group)
        if not isinstance(block, dict) or not block.get('time'):
            raise ValueError('missing group/time')
        if group != 'current':
            n = len(block['time'])
            if n < (24 if group == 'hourly' else 7):
                raise ValueError('short forecast')
            for field in required[group]:
                if not isinstance(block.get(field), list) or len(block[field]) != n:
                    raise ValueError('inconsistent forecast arrays')
        else:
            if not all(field in block for field in required[group]):
                raise ValueError('missing current fields')
            value = block.get('temperature_2m' if kind == 'weather' else 'wave_height')
            if not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError('missing current value')
    stamp = dt.datetime.fromisoformat(data['current']['time']).replace(tzinfo=dt.timezone(dt.timedelta(hours=9)))
    if abs(time.time() - stamp.timestamp()) > 6 * 3600:
        raise ValueError('upstream current time is too old or in the future')
    return data


def fetch(kind, area):
    if not enabled(kind):
        raise ValueError('source not approved')
    if kind not in PROVIDERS:
        return fetch_additional(kind, area)
    request = urllib.request.Request(upstream_url(kind, area), headers={'User-Agent': 'Umibiyori-Collector/1.0', 'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(4 * 1024 * 1024 + 1)
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError('response too large')
    return validate(kind, json.loads(raw))


class Store:
    def __init__(self, path, max_age=3600):
        self.path, self.max_age = str(path), max_age
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE IF NOT EXISTS points(id TEXT PRIMARY KEY, payload TEXT NOT NULL, expires REAL NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS settings(kind TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS areas(id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS schedule(kind TEXT, area TEXT, next_attempt REAL, failures INTEGER, PRIMARY KEY(kind,area))')
            if 'request_key' not in {row[1] for row in db.execute('PRAGMA table_info(schedule)')}:
                db.execute('ALTER TABLE schedule ADD COLUMN request_key TEXT')
            db.execute('CREATE TABLE IF NOT EXISTS snapshots(kind TEXT, area TEXT, payload TEXT, fetched REAL, attempted REAL, error TEXT, PRIMARY KEY(kind,area))')

        with self.connect() as db:
            saved=list(db.execute('SELECT kind,payload FROM settings'))
        for kind,raw in saved:
            if kind in SOURCES and SOURCES[kind]['legal_review']=='approved_with_conditions':
                SOURCES[kind]={**SOURCES[kind],**json.loads(raw)}

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def collect(self, kind, area_id, getter=fetch):
        if kind not in SOURCES or not enabled(kind):
            return False
        now = time.time()
        try:
            if not enabled(kind):
                raise ValueError('source not approved')
            area=self.areas().get(area_id)
            data = dict(getter(kind, area))
            data['_collector_request'] = upstream_url(kind,area) if kind in PROVIDERS else source_url(kind,area)
            with self.connect() as db:
                db.execute('INSERT INTO snapshots VALUES (?,?,?,?,?,NULL) ON CONFLICT(kind,area) DO UPDATE SET payload=excluded.payload,fetched=excluded.fetched,attempted=excluded.attempted,error=NULL',
                           (kind, area_id, json.dumps(data, allow_nan=False), now, now))
            self.save_schedule(kind, area_id, next_due(kind, time.time()), 0)
            return True
        except Exception as exc:
            # Store only the exception class; upstream URLs/credentials never enter logs/API.
            error = type(exc).__name__ + (':'+str(exc.code) if hasattr(exc,'code') else '')
            with self.connect() as db:
                db.execute('INSERT INTO snapshots VALUES (?,?,NULL,NULL,?,?) ON CONFLICT(kind,area) DO UPDATE SET attempted=excluded.attempted,error=excluded.error', (kind, area_id, now, error))
            with self.connect() as db:
                previous = db.execute('SELECT failures FROM schedule WHERE kind=? AND area=?',(kind,area_id)).fetchone()
            failures = (previous[0] if previous else 0) + 1
            delay = min(interval(kind), 60 * 2 ** min(failures-1,6))
            if hasattr(exc, 'headers'):
                retry = exc.headers.get('Retry-After','')
                if retry.isdigit(): delay = max(delay, min(int(retry),86400))
            self.save_schedule(kind,area_id,time.time()+delay,failures)
            logging.warning('collection failed kind=%s area=%s error=%s', kind, area_id, error)
            return False

    def areas(self):
        with self.connect() as db:
            custom = {key:json.loads(raw) for key,raw in db.execute('SELECT id,payload FROM areas')}
        with self.connect() as db:
            points={key:json.loads(raw) for key,raw in db.execute('SELECT id,payload FROM points WHERE expires>?',(time.time(),))}
        return {**AREAS,**custom,**points}

    def ensure_point(self,data):
        import hashlib
        if not isinstance(data,dict) or set(data)!={'latitude','longitude'}:
            raise ValueError('latitude and longitude only')
        lat,lon=data['latitude'],data['longitude']
        if any(not isinstance(v,(int,float)) or isinstance(v,bool) or not math.isfinite(v) for v in [lat,lon]) or not (-90<=lat<=90 and -180<=lon<=180):
            raise ValueError('invalid coordinates')
        lat,lon=round(lat,2),round(lon,2)
        key='point_'+hashlib.sha256(f'{lat:.2f},{lon:.2f}'.encode()).hexdigest()[:16]
        point={'name':'Temporary data point','lat':lat,'lon':lon,'cache_only':True}
        self.prune_points()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            exists=db.execute('SELECT 1 FROM points WHERE id=?',(key,)).fetchone()
            if not exists and db.execute('SELECT count(*) FROM points').fetchone()[0]>=32:
                raise ValueError('temporary point cache is full; try later')
            db.execute('INSERT INTO points VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET expires=excluded.expires',(key,json.dumps(point),time.time()+43200))
        return {'id':key,'latitude':lat,'longitude':lon,'expires_in_seconds':43200}

    def prune_points(self):
        with self.connect() as db:
            expired=[r[0] for r in db.execute('SELECT id FROM points WHERE expires<=?',(time.time(),))]
            for key in expired:
                db.execute('DELETE FROM snapshots WHERE area=?',(key,))
                db.execute('DELETE FROM schedule WHERE area=?',(key,))
                db.execute('DELETE FROM points WHERE id=?',(key,))

    def update_settings(self,kind,data):
        if kind not in SOURCES or SOURCES[kind]['legal_review']!='approved_with_conditions':
            raise ValueError('source has not been cleared for use')
        if not isinstance(data,dict) or set(data)!={'enabled','collection_interval_seconds','alignment_offset_seconds'}:
            raise ValueError('invalid schedule settings')
        period,offset=data['collection_interval_seconds'],data['alignment_offset_seconds']
        if not isinstance(data['enabled'],bool) or type(period) is not int or not SOURCES[kind].get('minimum_collection_interval_seconds',300)<=period<=86400 or (offset is not None and (type(offset) is not int or not 0<=offset<period)):
            raise ValueError('interval below operational minimum or above 86400 seconds; offset must be within interval')
        with self.connect() as db:
            db.execute('INSERT INTO settings VALUES (?,?) ON CONFLICT(kind) DO UPDATE SET payload=excluded.payload',(kind,json.dumps(data)))
        SOURCES[kind]={**SOURCES[kind],**data}
        return SOURCES[kind]

    def add_area(self, data):
        import secrets
        if not isinstance(data,dict) or set(data)!={'name','bounds'}:
            raise ValueError('name and bounds required')
        name=data['name']
        bounds=data['bounds']
        if not isinstance(name,str) or not name.strip() or len(name)>60 or not isinstance(bounds,dict) or set(bounds)!={'south','west','north','east'}:
            raise ValueError('invalid name/bounds')
        if not all(isinstance(v,(float,int)) and not isinstance(v,bool) and math.isfinite(v) for v in bounds.values()):
            raise ValueError('finite coordinates required')
        south,west,north,east=(bounds[k] for k in ['south','west','north','east'])
        if not (-90<=south<north<=90 and -180<=west<east<=180) or east-west>180:
            raise ValueError('bounds must be ordered and span at most 180 degrees; split dateline regions')
        area={'name':name.strip(),'bounds':bounds,'lat':round((south+north)/2,5),'lon':round((west+east)/2,5),'custom':True,'sampling':'center_point'}
        key='user_'+secrets.token_hex(6)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT COUNT(*) FROM areas').fetchone()[0]>=24:
                raise ValueError('maximum 24 custom areas')
            db.execute('INSERT INTO areas VALUES (?,?)',(key,json.dumps(area,ensure_ascii=False)))
        return key,area

    def delete_area(self,key):
        with self.connect() as db:
            result=db.execute('DELETE FROM areas WHERE id=?',(key,))
            if not result.rowcount:return False
            db.execute('DELETE FROM snapshots WHERE area=?',(key,))
            db.execute('DELETE FROM schedule WHERE area=?',(key,))
        return True

    def save_schedule(self, kind, area, due, failures):
        with self.connect() as db:
            db.execute('INSERT INTO schedule(kind,area,next_attempt,failures,request_key) VALUES (?,?,?,?,?) ON CONFLICT(kind,area) DO UPDATE SET next_attempt=excluded.next_attempt,failures=excluded.failures,request_key=excluded.request_key', (kind,area,due,failures,self.request_key(kind,area)))

    def request_key(self,kind,area_id):
        area=self.areas().get(area_id)
        if area is None and kind not in GLOBAL_KINDS:return ''
        url=upstream_url(kind,area) if kind in PROVIDERS else source_url(kind,area)
        return json.dumps([url,interval(kind),SOURCES[kind]['alignment_offset_seconds']])

    def due_jobs(self, now=None):
        now = time.time() if now is None else now
        with self.connect() as db:
            scheduled = {(k,a): (due,key) for k,a,due,key in db.execute('SELECT kind,area,next_attempt,request_key FROM schedule')}
        return [(k,a) for k,a in jobs(self) if (k,a) not in scheduled or scheduled[(k,a)][0]<=now or scheduled[(k,a)][1]!=self.request_key(k,a)]

    def timing(self, kind, area):
        with self.connect() as db:
            row = db.execute('SELECT next_attempt,failures FROM schedule WHERE kind=? AND area=?',(kind,area)).fetchone()
        return {'next_attempt_at': dt.datetime.fromtimestamp(row[0],dt.timezone.utc).isoformat() if row else None,
                'consecutive_failures': row[1] if row else 0,
                'collection_interval_seconds': interval(kind)}

    def read(self, kind, area_id):
        with self.connect() as db:
            row = db.execute('SELECT payload,fetched,attempted,error FROM snapshots WHERE kind=? AND area=?', (kind, area_id)).fetchone()
        if not row or row[0] is None:
            return None
        data = json.loads(row[0])
        age = max(0, time.time() - row[1])
        source = SOURCES[kind]
        data['_meta'] = {'provider': 'Open-Meteo' if kind in PROVIDERS else source['name'], 'license': source['license'], 'attribution': source['attribution'], 'terms_urls': source['terms_urls'], 'legal_review': source['legal_review'], 'area': area_id,
                         'fetched_at': dt.datetime.fromtimestamp(row[1], dt.timezone.utc).isoformat(),
                         'age_seconds': round(age), 'stale': age > max(self.max_age, interval(kind)*2),
                         'last_collection_failed': row[3] is not None,
                         'last_attempt_at': dt.datetime.fromtimestamp(row[2],dt.timezone.utc).isoformat(),
                         'source_url': data.pop('_collector_request', PROVIDERS[kind][0] if kind in PROVIDERS else source_url(kind,self.areas().get(area_id))),
                         **self.timing(kind,area_id)}
        return data


def time_window(data, window, now=None):
    now=dt.datetime.now(dt.timezone.utc) if now is None else now
    history=window=='history'
    start=now-dt.timedelta(hours=12) if history else now
    end=now if history else now+dt.timedelta(hours=int(window))
    times=data['hourly']['time']
    indices=[]
    for i,t in enumerate(times):
        stamp=dt.datetime.fromisoformat(t).replace(tzinfo=dt.timezone(dt.timedelta(hours=9)))
        if (start<=stamp<=end if history else start<stamp<=end):indices.append(i)
    hourly={key:[values[i] for i in indices] for key,values in data['hourly'].items() if isinstance(values,list)}
    return {**data,'hourly':hourly,'_window':{'applies_to':'hourly','mode':window,'start':start.isoformat(),'end':end.isoformat(),'sample_count':len(indices),'data_type':'model_estimate_not_observation','missing_samples_are_not_filled':True}}


def make_handler(store):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlsplit(self.path)
            if parsed.path == '/health':
                return self.reply(200, {'status': 'alive'})
            if parsed.path == '/api/v1/sources':
                return self.reply(200,SOURCES)
            if parsed.path == '/api/v1/areas':
                return self.reply(200, AREAS)
            if parsed.path == '/api/v1/admin/settings':
                return self.reply(200,SOURCES)
            if parsed.path == '/api/v1/admin/areas':
                return self.reply(200,store.areas())
            if parsed.path in ('/ready', '/api/v1/status'):
                chosen=urllib.parse.parse_qs(parsed.query).get('area',['tokyo'])[0]
                if parsed.path=='/api/v1/status' and chosen not in store.areas():return self.reply(400,{'error':'invalid_area'})
                pairs=jobs(store) if parsed.path=='/ready' else [(k,a) for k,a in jobs(store) if a in (chosen,'_global')]
                states={kind:{area:store.read(kind,area) for k,area in pairs if k==kind} for kind in {k for k,a in pairs}}
                ready = all(d and not d['_meta']['stale'] for group in states.values() for d in group.values())
                return self.reply(200 if ready or parsed.path.endswith('/status') else 503,
                                  {'ready': ready, 'datasets': {k: {a: d['_meta'] if d else {'available': False, **store.timing(k,a)} for a, d in group.items()} for k, group in states.items()}})
            kind = parsed.path.removeprefix('/api/v1/')
            if parsed.path not in tuple('/api/v1/'+k for k in SOURCES if enabled(k)):
                return self.reply(404, {'error': 'not_found'})
            query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            if kind in GLOBAL_KINDS:
                if query: return self.reply(400,{'error':'no_area_for_global_dataset'})
                data=store.read(kind,'_global')
                return self.reply(200,data) if data else self.reply(503,{'error':'not_collected_yet'},retry=True)
            allowed={'area','window'} if kind in PROVIDERS else {'area'}
            if not set(query)<=allowed or 'area' not in query or len(query['area']) != 1 or query['area'][0] not in store.areas():
                return self.reply(400, {'error': 'invalid_area', 'valid_areas': list(store.areas())})
            data = store.read(kind, query['area'][0])
            if data is None:
                return self.reply(503, {'error': 'not_collected_yet'}, retry=True)
            if 'window' in query:
                if len(query['window'])!=1 or query['window'][0] not in ('history','24','36'):
                    return self.reply(400,{'error':'window_must_be_history_24_or_36'})
                data=time_window(data,query['window'][0])
            return self.reply(200, data)

        def origin_ok(self):
            origin=self.headers.get('Origin')
            return not origin or urllib.parse.urlsplit(origin).netloc.lower()==self.headers.get('Host','').lower()

        def do_POST(self):
            allowed=self.path in ('/api/v1/points','/api/v1/admin/areas') or self.path.startswith('/api/v1/admin/schedules/')
            if not allowed:return self.reply(404,{'error':'not_found'})
            if not self.origin_ok():return self.reply(403,{'error':'cross_origin_denied'})
            if self.headers.get('Content-Type','').split(';')[0]!='application/json':
                return self.reply(415,{'error':'json_required'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=4096:raise ValueError('body limit 4096')
                data=json.loads(self.rfile.read(size))
                if self.path=='/api/v1/points':return self.reply(200,store.ensure_point(data))
                if self.path.startswith('/api/v1/admin/schedules/'):
                    return self.reply(200,store.update_settings(self.path.rsplit('/',1)[-1],data))
                key,area=store.add_area(data)
                return self.reply(201,{'id':key,**area})
            except (ValueError,UnicodeError) as exc:
                return self.reply(400,{'error':str(exc)})

        def do_DELETE(self):
            if not self.origin_ok():return self.reply(403,{'error':'cross_origin_denied'})
            prefix='/api/v1/admin/areas/'
            if not self.path.startswith(prefix):return self.reply(404,{'error':'not_found'})
            removed=store.delete_area(self.path[len(prefix):])
            return self.reply(200 if removed else 404,{'deleted':removed})

        def reply(self, status, data, retry=False):
            raw = json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            if retry:
                self.send_header('Retry-After', '30')
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *args):
            pass
    return Handler


def jobs(store=None):
    return [(kind,area) for kind in SOURCES if enabled(kind)
            for area in (['_global'] if kind in GLOBAL_KINDS else (store.areas() if store else AREAS))]


def collect_loop(store, stop):
    while not stop.is_set():
        store.prune_points()
        due = store.due_jobs()
        if due:
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                list(pool.map(lambda pair: store.collect(*pair), due))
            logging.info('collection cycle complete datasets=%s',len(due))
        stop.wait(10)


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    store = Store(os.environ.get('DATA_PATH', '/data/ocean.sqlite3'), max_age=3600)
    stop = threading.Event()
    server = ThreadingHTTPServer(('0.0.0.0', int(os.environ.get('PORT', '8080'))), make_handler(store))
    def shutdown(*_):
        stop.set()
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    worker = threading.Thread(target=collect_loop, args=(store, stop), daemon=True)
    worker.start()
    try:
        server.serve_forever()
    finally:
        stop.set()
        server.server_close()
        worker.join(timeout=25)


if __name__ == '__main__':
    main()
