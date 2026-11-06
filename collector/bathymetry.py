"""GEBCO 2026 subsets through the official CEDA OPeNDAP service."""
import math
import re
import urllib.request

BASE='https://dap.ceda.ac.uk/thredds/dodsC/bodc/gebco/global/gebco_2026/ice_surface_elevation/netcdf/GEBCO_2026.nc'
KINDS={'bathymetry','bathymetry-base'}

def index(value,offset,count):
    return max(0,min(count-1,round((value+offset)*240-.5)))

def url(kind,area=None):
    if kind=='bathymetry-base':query='elevation[0:480:43199][0:480:86399]'
    else:
        south,north=max(-90,area['lat']-1),min(90,area['lat']+1)
        west,east=max(-180,area['lon']-1),min(180,area['lon']+1)
        query=f'elevation[{index(south,90,43200)}:2:{index(north,90,43200)}][{index(west,180,86400)}:2:{index(east,180,86400)}]'
    return BASE+'.ascii?'+query

def parse(raw,global_grid=False):
    text=raw.decode('utf-8')
    match=re.search(r'elevation\.elevation\[(\d+)\]\[(\d+)\]\s*\n(.*?)\n\s*elevation\.lat\[\d+\]\s*\n(.*?)\n\s*elevation\.lon\[\d+\]\s*\n(.*)',text,re.S)
    if not match:raise ValueError('unexpected GEBCO subset format')
    rows,cols=int(match[1]),int(match[2])
    if not 2<=rows<=300 or not 2<=cols<=300:raise ValueError('grid size limit')
    lats=[float(x.strip()) for x in match[4].strip().split(',')]
    lons=[float(x.strip()) for x in match[5].strip().split(',')]
    heights=[]
    for line in match[3].strip().splitlines():
        values=line.split(',')[1:]
        if len(values)!=cols:raise ValueError('bad grid row')
        for value in values:
            h=float(value)
            heights.append(h if math.isfinite(h) and -12000<=h<=9000 else None)
    if len(lats)!=rows or len(lons)!=cols or len(heights)!=rows*cols:raise ValueError('incomplete grid')
    if any(b<=a for a,b in zip(lats,lats[1:])) or any(b<=a for a,b in zip(lons,lons[1:])):raise ValueError('unordered grid')
    return {'product':'GEBCO_2026 Grid (ice surface)','latitude':lats,'longitude':lons,'height_m':heights,
            'shape':[rows,cols],'global':global_grid,'vertical_datum':'Mean Sea Level (some shallow-water sources differ)',
            'horizontal_datum':'WGS84','native_resolution_arcseconds':15,
            'sampled_resolution_degrees':round(lats[1]-lats[0],7),'units':'m',
            'value_convention':'negative = below mean sea level; positive = land/ice surface',
            'citation':'GEBCO Bathymetric Compilation Group 2026 (2026), GEBCO_2026 Grid. doi:10.5285/4f68d5c7-45eb-f999-e063-7086abc036fa',
            'not_for_navigation':True,'transformation':'海日和が間引き抽出。表示時に補間。元の標高・水深値の予報計算はしない。'}

def fetch(kind,area=None):
    req=urllib.request.Request(url(kind,area),headers={'User-Agent':'Umibiyori-Collector/1.0'})
    with urllib.request.urlopen(req,timeout=30) as response:raw=response.read(8*1024*1024+1)
    if len(raw)>8*1024*1024:raise ValueError('grid response too large')
    return parse(raw,kind=='bathymetry-base')
