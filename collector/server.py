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

AREAS = json.loads((Path(__file__).parent / 'areas.json').read_text())
PROVIDERS = {
    'weather': ('https://api.open-meteo.com/v1/forecast', {
        'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,weather_code,wind_speed_10m',
        'hourly': 'temperature_2m,precipitation_probability,weather_code,is_day',
        'daily': 'weather_code,temperature_2m_max,temperature_2m_min,sunset,precipitation_probability_max',
        'wind_speed_unit': 'ms', 'forecast_days': '7'}),
    'marine': ('https://marine-api.open-meteo.com/v1/marine', {
        'current': 'wave_height,wave_direction,wave_period,sea_surface_temperature',
        'hourly': 'wave_height,wave_direction,wave_period', 'forecast_days': '3'})}


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
            db.execute('CREATE TABLE IF NOT EXISTS snapshots(kind TEXT, area TEXT, payload TEXT, fetched REAL, attempted REAL, error TEXT, PRIMARY KEY(kind,area))')

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def collect(self, kind, area_id, getter=fetch):
        now = time.time()
        try:
            data = getter(kind, AREAS[area_id])
            with self.connect() as db:
                db.execute('INSERT INTO snapshots VALUES (?,?,?,?,?,NULL) ON CONFLICT(kind,area) DO UPDATE SET payload=excluded.payload,fetched=excluded.fetched,attempted=excluded.attempted,error=NULL',
                           (kind, area_id, json.dumps(data, allow_nan=False), now, now))
            return True
        except Exception as exc:
            # Store only the exception class; upstream URLs/credentials never enter logs/API.
            error = type(exc).__name__
            with self.connect() as db:
                db.execute('INSERT INTO snapshots VALUES (?,?,NULL,NULL,?,?) ON CONFLICT(kind,area) DO UPDATE SET attempted=excluded.attempted,error=excluded.error', (kind, area_id, now, error))
            logging.warning('collection failed kind=%s area=%s error=%s', kind, area_id, error)
            return False

    def read(self, kind, area_id):
        with self.connect() as db:
            row = db.execute('SELECT payload,fetched,attempted,error FROM snapshots WHERE kind=? AND area=?', (kind, area_id)).fetchone()
        if not row or row[0] is None:
            return None
        data = json.loads(row[0])
        age = max(0, time.time() - row[1])
        data['_meta'] = {'provider': 'Open-Meteo', 'license': 'CC BY 4.0', 'area': area_id,
                         'fetched_at': dt.datetime.fromtimestamp(row[1], dt.timezone.utc).isoformat(),
                         'age_seconds': round(age), 'stale': age > self.max_age,
                         'last_collection_failed': row[3] is not None, 'source_url': upstream_url(kind, AREAS[area_id])}
        return data


def make_handler(store):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlsplit(self.path)
            if parsed.path == '/health':
                return self.reply(200, {'status': 'alive'})
            if parsed.path == '/api/v1/areas':
                return self.reply(200, AREAS)
            if parsed.path in ('/ready', '/api/v1/status'):
                states = {kind: {area: store.read(kind, area) for area in AREAS} for kind in PROVIDERS}
                ready = all(d and not d['_meta']['stale'] for group in states.values() for d in group.values())
                return self.reply(200 if ready or parsed.path.endswith('/status') else 503,
                                  {'ready': ready, 'datasets': {k: {a: d['_meta'] if d else {'available': False} for a, d in group.items()} for k, group in states.items()}})
            kind = parsed.path.removeprefix('/api/v1/')
            if parsed.path not in ('/api/v1/weather', '/api/v1/marine'):
                return self.reply(404, {'error': 'not_found'})
            query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            if set(query) != {'area'} or len(query['area']) != 1 or query['area'][0] not in AREAS:
                return self.reply(400, {'error': 'invalid_area', 'valid_areas': list(AREAS)})
            data = store.read(kind, query['area'][0])
            if data is None:
                return self.reply(503, {'error': 'not_collected_yet'}, retry=True)
            return self.reply(200, data)

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


def collect_loop(store, stop, interval):
    while not stop.is_set():
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda pair: store.collect(*pair), ((k, a) for k in PROVIDERS for a in AREAS)))
        logging.info('collection cycle complete')
        stop.wait(interval)


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    interval = max(300, int(os.environ.get('COLLECT_INTERVAL_SECONDS', '1800')))
    store = Store(os.environ.get('DATA_PATH', '/data/ocean.sqlite3'), max_age=max(interval * 2, 3600))
    stop = threading.Event()
    server = ThreadingHTTPServer(('0.0.0.0', int(os.environ.get('PORT', '8080'))), make_handler(store))
    def shutdown(*_):
        stop.set()
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    worker = threading.Thread(target=collect_loop, args=(store, stop, interval), daemon=True)
    worker.start()
    try:
        server.serve_forever()
    finally:
        stop.set()
        server.server_close()
        worker.join(timeout=25)


if __name__ == '__main__':
    main()
