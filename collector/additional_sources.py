"""Adapters whose specific reuse conditions are recorded in sources.json."""
import datetime as dt
import io
import json
from pathlib import Path
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

SOURCES = json.loads((Path(__file__).parent / 'sources.json').read_text())
GLOBAL_KINDS = {'jma-marine-bulletins', 'jma-typhoon-bulletins'}
JMA = 'https://www.data.jma.go.jp/developer/xml/feed/'
ERDDAP = 'https://coastwatch.pfeg.noaa.gov/erddap/griddap/ncdcOisst21Agg_LonPM180.json'
NS = '{http://www.w3.org/2005/Atom}'


def enabled(kind):
    item = SOURCES[kind]
    return item['enabled'] and item['legal_review'] == 'approved_with_conditions'


def interval(kind):
    return SOURCES[kind]['collection_interval_seconds']


def next_due(kind, now):
    period = interval(kind)
    offset = SOURCES[kind]['alignment_offset_seconds']
    return now + period if offset is None else ((now - offset) // period + 1) * period + offset


def source_url(kind, area=None):
    if kind in GLOBAL_KINDS:
        return JMA + ('regular_l.xml' if kind == 'jma-marine-bulletins' else 'extra_l.xml')
    return ERDDAP + '?' + urllib.parse.quote(f"sst[(last)][(0.0)][({area['lat']})][({area['lon']})]", safe='[]().')


def request_bytes(url, limit):
    req = urllib.request.Request(url, headers={'User-Agent': 'Umibiyori-Collector/1.0'})
    with urllib.request.urlopen(req, timeout=25) as response:
        raw = response.read(limit+1)
    if len(raw) > limit:
        raise ValueError('response too large')
    return raw


def parse_feed(raw, kind):
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('XML declarations forbidden')
    entries, updated = [], None
    keyword = '海上' if kind == 'jma-marine-bulletins' else '台風'
    for event, element in ET.iterparse(io.BytesIO(raw), events=('end',)):
        if element.tag == NS+'updated' and updated is None:
            updated = element.text
        if element.tag != NS+'entry':
            continue
        title = element.findtext(NS+'title', '')
        if keyword in title:
            link = element.find(NS+'link')
            url = link.get('href','') if link is not None else ''
            parsed = urllib.parse.urlsplit(url)
            if parsed.scheme == 'https' and parsed.hostname == 'www.data.jma.go.jp' and parsed.path.startswith('/developer/xml/data/'):
                entries.append({'id': element.findtext(NS+'id',''), 'title': title,
                                'issued_at': element.findtext(NS+'updated',''),
                                'summary': element.findtext(NS+'content',''), 'source_url': url})
        element.clear()
    if not updated:
        raise ValueError('feed time missing')
    stamp = dt.datetime.fromisoformat(updated.replace('Z','+00:00'))
    if abs((dt.datetime.now(dt.timezone.utc)-stamp).total_seconds()) > 86400:
        raise ValueError('feed too old')
    return {'feed_updated_at': updated, 'items': sorted(entries,key=lambda e:e['issued_at'],reverse=True)[:100],
            'scope': 'Recent feed entries, NOT a list of currently active warnings',
            'transformation': '海日和が対象電文の索引を抽出・JSON化。タイトル・概要は原文。編集責任：海日和。'}


def fetch_additional(kind, area):
    if not enabled(kind):
        raise ValueError('source not approved')
    raw = request_bytes(source_url(kind,area), 20*1024*1024 if kind in GLOBAL_KINDS else 65536)
    if kind in GLOBAL_KINDS:
        return parse_feed(raw,kind)
    table = json.loads(raw)['table']
    row = dict(zip(table['columnNames'],table['rows'][0]))
    value = row['sst']
    if not isinstance(value,(float,int)) or not -3 <= value <= 45:
        raise ValueError('invalid SST')
    when = dt.datetime.fromisoformat(row['time'].replace('Z','+00:00'))
    if not 0 <= (dt.datetime.now(dt.timezone.utc)-when).total_seconds() <= 30*86400:
        raise ValueError('analysis time outside final product window')
    return {'data_time':row['time'], 'latitude':row['latitude'],'longitude':row['longitude'],
            'sea_surface_temperature':value,'units':'degree_C',
            'product':'NOAA OISST v2.1 Final','product_type':'delayed_daily_analysis',
            'note':'約2週間遅れの確定解析。現在の観測水温・予報ではありません。'}
