import {readSettings,writeSettings,validLocalArea} from './browser-settings.mjs';
import {decodeGsiHeight} from './gis-terrain.mjs';
const $=id=>document.getElementById(id);
const C=globalThis.Cesium;
let viewer,selection,first,selecting=false,drawn,centerPoint;
const emptyTerrain=()=>new C.EllipsoidTerrainProvider();
function tileTerrain(){
 const scheme=new C.WebMercatorTilingScheme();
 const cache=new Map();
 async function pixels(z,x,y){
  const key=`${z}/${x}/${y}`;
  if(!cache.has(key)){
   if(cache.size>80)cache.delete(cache.keys().next().value);
   cache.set(key,(async()=>{const r=await fetch(`https://cyberjapandata.gsi.go.jp/xyz/dem_png/${key}.png`);if(!r.ok)throw Error('No DEM');const image=await createImageBitmap(await r.blob());const canvas=document.createElement('canvas');canvas.width=256;canvas.height=256;const ctx=canvas.getContext('2d',{willReadFrequently:true});ctx.drawImage(image,0,0);image.close();return ctx.getImageData(0,0,256,256).data;})().catch(()=>null));
  }
  return cache.get(key);
 }
 return new C.CustomHeightmapTerrainProvider({width:64,height:64,tilingScheme:scheme,credit:new C.Credit('<a href="https://maps.gsi.go.jp/development/ichiran.html">国土地理院 DEM10Bを海日和が3D地形に加工</a>',true),callback:async(x,y,level)=>{
  const values=new Float32Array(64*64);const rect=scheme.tileXYToRectangle(x,y,level);
  if(rect.east<C.Math.toRadians(122)||rect.west>C.Math.toRadians(155)||rect.north<C.Math.toRadians(20)||rect.south>C.Math.toRadians(46))return values;
  const z=Math.min(level,14),scale=2**(level-z),tx=Math.floor(x/scale),ty=Math.floor(y/scale),rgba=await pixels(z,tx,ty);
  if(!rgba)return values;
  for(let row=0;row<64;row++)for(let col=0;col<64;col++){
   const px=Math.min(255,Math.floor(((x%scale)+(col/63))/scale*255)),py=Math.min(255,Math.floor(((y%scale)+(row/63))/scale*255));const i=(py*256+px)*4;values[row*64+col]=decodeGsiHeight(rgba[i],rgba[i+1],rgba[i+2],rgba[i+3]);
  }
  return values;
 }});
}
function boundsFromInputs(){const b={};for(const k of ['south','west','north','east']){if(!$('bound-'+k).value.trim())throw Error('すべての座標を入力してください。');b[k]=Number($('bound-'+k).value);}if(Object.values(b).some(v=>!Number.isFinite(v))||b.south>=b.north||b.west>=b.east||b.south< -90||b.north>90||b.west< -180||b.east>180||b.east-b.west>180)throw Error('緯度・経度の範囲を確認してください。日付変更線をまたぐ場合は海域を分割してください。');return b;}
function fillBounds(b){for(const k of Object.keys(b))$('bound-'+k).value=Number(b[k]).toFixed(5);}
function draw(b,name='選択海域',fly=false){
 selection=b;if(!viewer)return;
 if(drawn)viewer.entities.remove(drawn);if(centerPoint)viewer.entities.remove(centerPoint);
 drawn=viewer.entities.add({rectangle:{coordinates:C.Rectangle.fromDegrees(b.west,b.south,b.east,b.north),material:C.Color.fromCssColorString('#4eafbd').withAlpha(.25),outline:true,outlineColor:C.Color.CYAN}});
 centerPoint=viewer.entities.add({position:C.Cartesian3.fromDegrees((b.west+b.east)/2,(b.south+b.north)/2),point:{pixelSize:9,color:C.Color.ORANGE,disableDepthTestDistance:Number.POSITIVE_INFINITY},label:{text:name,font:'14px sans-serif',pixelOffset:new C.Cartesian2(0,-24),showBackground:true,disableDepthTestDistance:Number.POSITIVE_INFINITY}});
 if(fly)viewer.camera.flyTo({destination:C.Rectangle.fromDegrees(Math.max(-180,b.west-.3),Math.max(-90,b.south-.3),Math.min(180,b.east+.3),Math.min(90,b.north+.3)),duration:.7});
}
function initMap(){
 if(!C){$('gis-status').textContent='GISライブラリを読み込めません。座標入力で海域を追加できます。';return;}
 try{
  C.Ion.defaultAccessToken=undefined;
  viewer=new C.Viewer('gis-map',{baseLayer:false,terrainProvider:emptyTerrain(),animation:false,timeline:false,geocoder:false,baseLayerPicker:false,homeButton:false,fullscreenButton:false,navigationHelpButton:false,sceneModePicker:false,selectionIndicator:false,infoBox:false,requestRenderMode:true});
  viewer.imageryLayers.addImageryProvider(new C.UrlTemplateImageryProvider({url:'https://tile.openstreetmap.org/{z}/{x}/{y}.png',maximumLevel:19,credit:new C.Credit('<a href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors</a>',true)}));
  const prefs=readSettings(localStorage);if(prefs.mapView&&['lon','lat','height','heading','pitch','roll'].every(k=>Number.isFinite(prefs.mapView[k]))){const v=prefs.mapView;viewer.camera.setView({destination:C.Cartesian3.fromDegrees(v.lon,v.lat,v.height),orientation:{heading:v.heading,pitch:v.pitch,roll:v.roll}});}
  viewer.camera.moveEnd.addEventListener(()=>{try{const p=viewer.camera.positionCartographic;writeSettings(localStorage,{mapView:{lon:C.Math.toDegrees(p.longitude),lat:C.Math.toDegrees(p.latitude),height:p.height,heading:viewer.camera.heading,pitch:viewer.camera.pitch,roll:viewer.camera.roll},sceneMode:viewer.scene.mode});}catch{}});
  viewer.scene.globe.baseColor=C.Color.fromCssColorString('#afcbd4');
  viewer.screenSpaceEventHandler.setInputAction(click=>{
   if(!selecting)return;
   const ray=viewer.camera.getPickRay(click.position);const cart=viewer.scene.globe.pick(ray,viewer.scene)||viewer.camera.pickEllipsoid(click.position);if(!cart)return;
   const p=C.Cartographic.fromCartesian(cart),point={lat:C.Math.toDegrees(p.latitude),lon:C.Math.toDegrees(p.longitude)};
   if(!first){first=point;$('gis-status').textContent='対角のもう1点を選択してください。';return;}
   const b={south:Math.min(first.lat,point.lat),north:Math.max(first.lat,point.lat),west:Math.min(first.lon,point.lon),east:Math.max(first.lon,point.lon)};fillBounds(b);draw(b);selecting=false;first=null;$('draw-area').textContent='地図で範囲選択';$('gis-status').textContent='範囲を選択しました。名前を付けて保存してください。';
  },C.ScreenSpaceEventType.LEFT_CLICK);
  $('view-2d').onclick=()=>{viewer.scene.morphTo2D(.5);$('gis-status').textContent='2D表示';};
  $('view-3d').onclick=()=>{viewer.scene.morphTo3D(.5);$('gis-status').textContent='3D表示：右ドラッグで回転・傾斜できます。';};
  $('terrain').onchange=()=>{try{writeSettings(localStorage,{terrain:$('terrain').checked});}catch{};viewer.terrainProvider=$('terrain').checked?tileTerrain():emptyTerrain();viewer.scene.requestRender();$('gis-status').textContent=$('terrain').checked?'日本のDEM提供範囲で陸上地形を表示します。未提供域・海底は実地形を表しません。':'地形の起伏をオフにしました。';};
  $('tilt').onclick=()=>{viewer.scene.morphTo3D(0);const b=selection||boundsFromInputs(),lon=(b.west+b.east)/2,lat=(b.south+b.north)/2,span=Math.max((b.north-b.south)*111000,(b.east-b.west)*111000*Math.cos(C.Math.toRadians(lat))),height=Math.max(8000,Math.min(2000000,span));viewer.camera.flyTo({destination:C.Cartesian3.fromDegrees(lon,Math.max(-89,lat-height/111000),height),orientation:{heading:0,pitch:C.Math.toRadians(-45),roll:0},duration:.8});};
 }catch(e){$('gis-status').textContent='この環境では3D表示を利用できません。座標入力で海域を追加できます。';}
}
export async function setupAreas(cities){
 initMap();
 const select=$('city');
 function showCurrent(fly=true){const area=cities[select.value];if(!area)return;const b=area.bounds||{south:area.lat-.25,west:area.lon-.25,north:area.lat+.25,east:area.lon+.25};fillBounds(b);draw(b,area.name,fly);$('delete-area').disabled=!area.custom;}
 function remember(){const local={};for(const [key,a] of Object.entries(cities))if(a.custom)local[key]={name:a.name,bounds:a.bounds,lat:a.lat,lon:a.lon,custom:true};writeSettings(localStorage,{areas:local,selected:select.value});}
 async function readAreas(){
  let prefs={};try{prefs=readSettings(localStorage);}catch{}
  for(const [key,a] of Object.entries(prefs.areas||{}))if(key.startsWith('local_')&&validLocalArea(a))cities[key]={...a,custom:true,lat:(a.bounds.south+a.bounds.north)/2,lon:(a.bounds.west+a.bounds.east)/2};
  select.replaceChildren();for(const [key,a] of Object.entries(cities)){const opt=document.createElement('option');opt.value=key;opt.textContent=a.name+(a.custom?' · このブラウザ':'');select.append(opt);}
  if(cities[prefs.selected])select.value=prefs.selected;
  showCurrent(!prefs.mapView);if(prefs.terrain&&viewer){$('terrain').checked=true;$('terrain').dispatchEvent(new Event('change'));}
  if(viewer&&prefs.sceneMode===2)viewer.scene.morphTo2D(0);
 }
 $('draw-area').onclick=()=>{if(!viewer){$('gis-status').textContent='座標を入力して保存してください。';return;}selecting=!selecting;first=null;$('draw-area').textContent=selecting?'選択を中止':'地図で範囲選択';$('gis-status').textContent=selecting?'矩形海域の対角になる2点を順に選択してください。':'選択を中止しました。';};
 for(const key of ['south','west','north','east'])$('bound-'+key).addEventListener('change',()=>{try{draw(boundsFromInputs());}catch(e){$('gis-status').textContent=e.message;}});
 $('save-area').onclick=()=>{try{const b=boundsFromInputs(),name=$('area-name').value.trim();if(!name)throw Error('海域名を入力してください。');if(Object.values(cities).filter(a=>a.custom).length>=24)throw Error('このブラウザに保存できる海域は24件です。');const id='local_'+crypto.randomUUID().replaceAll('-','');const area={name,bounds:b,lat:(b.south+b.north)/2,lon:(b.west+b.east)/2,custom:true};const old=select.value;cities[id]=area;select.value=old;const opt=document.createElement('option');opt.value=id;opt.textContent=name+' · このブラウザ';select.append(opt);select.value=id;try{remember();}catch(e){delete cities[id];opt.remove();select.value=old;throw Error('ブラウザに保存できません。ストレージ設定を確認してください。');}select.dispatchEvent(new Event('change'));$('gis-status').textContent='海域名・範囲をこのブラウザに保存しました。初回収集後に「更新」で表示できます。';}catch(e){$('gis-status').textContent=e.message;}};
 $('delete-area').onclick=()=>{const key=select.value;if(!cities[key]?.custom)return;try{const next={};for(const [id,a] of Object.entries(cities))if(a.custom&&id!==key)next[id]=a;writeSettings(localStorage,{areas:next,selected:'tokyo'});delete cities[key];select.querySelector(`option[value="${key}"]`)?.remove();select.value='tokyo';select.dispatchEvent(new Event('change'));$('gis-status').textContent='このブラウザから海域を削除しました。';}catch{$('gis-status').textContent='ブラウザ設定を保存できません。';}};
 select.addEventListener('change',()=>{try{remember();}catch{}});
 select.addEventListener('change',()=>showCurrent());
 try{await readAreas();}catch(e){showCurrent();$('gis-status').textContent=e.message+'。既定海域を表示します。';}
}

export async function prepareArea(area){if(!area.custom)return;const r=await fetch('/api/v1/points',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({latitude:area.lat,longitude:area.lon})});const d=await r.json();if(!r.ok)throw Error(d.error||'地点の準備ができません');area.apiArea=d.id;}
