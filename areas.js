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
  $('terrain').onchange=()=>{viewer.terrainProvider=$('terrain').checked?tileTerrain():emptyTerrain();viewer.scene.requestRender();$('gis-status').textContent=$('terrain').checked?'日本のDEM提供範囲で陸上地形を表示します。未提供域・海底は実地形を表しません。':'地形の起伏をオフにしました。';};
  $('tilt').onclick=()=>{viewer.scene.morphTo3D(0);const b=selection||boundsFromInputs(),lon=(b.west+b.east)/2,lat=(b.south+b.north)/2;viewer.camera.flyTo({destination:C.Cartesian3.fromDegrees(lon,Math.max(-84,lat-1.2),130000),orientation:{heading:0,pitch:C.Math.toRadians(-45),roll:0},duration:.8});};
 }catch(e){$('gis-status').textContent='この環境では3D表示を利用できません。座標入力で海域を追加できます。';}
}
export async function setupAreas(cities){
 initMap();
 const select=$('city');
 function showCurrent(){const area=cities[select.value];if(!area)return;const b=area.bounds||{south:area.lat-.25,west:area.lon-.25,north:area.lat+.25,east:area.lon+.25};fillBounds(b);draw(b,area.name,true);$('delete-area').disabled=!area.custom;}
 async function readAreas(){const r=await fetch('/api/v1/areas');if(!r.ok)throw Error('海域一覧を取得できません');const areas=await r.json();for(const key of Object.keys(cities))delete cities[key];Object.assign(cities,areas);select.replaceChildren();for(const [key,a] of Object.entries(cities)){const opt=document.createElement('option');opt.value=key;opt.textContent=a.name+(a.custom?' · 追加海域':'');select.append(opt);}let saved;try{saved=localStorage.getItem('umibiyori-area');}catch{}if(cities[saved])select.value=saved;showCurrent();}
 $('draw-area').onclick=()=>{if(!viewer){$('gis-status').textContent='座標を入力して保存してください。';return;}selecting=!selecting;first=null;$('draw-area').textContent=selecting?'選択を中止':'地図で範囲選択';$('gis-status').textContent=selecting?'矩形海域の対角になる2点を順に選択してください。':'選択を中止しました。';};
 for(const key of ['south','west','north','east'])$('bound-'+key).addEventListener('change',()=>{try{draw(boundsFromInputs());}catch(e){$('gis-status').textContent=e.message;}});
 $('save-area').onclick=async()=>{const button=$('save-area');button.disabled=true;try{const b=boundsFromInputs(),name=$('area-name').value.trim();if(!name)throw Error('海域名を入力してください。');const r=await fetch('/api/v1/areas',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,bounds:b})});const d=await r.json();if(!r.ok)throw Error(d.error||'保存できません');cities[d.id]=d;const opt=document.createElement('option');opt.value=d.id;opt.textContent=d.name+' · 追加海域';select.append(opt);select.value=d.id;select.dispatchEvent(new Event('change'));$('gis-status').textContent='保存しました。初回のデータ収集には数分かかることがあります。収集後に「更新」を押してください。';}catch(e){$('gis-status').textContent=e.message;}finally{button.disabled=false;}};
 $('delete-area').onclick=async()=>{const key=select.value;if(!cities[key]?.custom)return;try{const r=await fetch('/api/v1/areas/'+encodeURIComponent(key),{method:'DELETE'});if(!r.ok)throw Error('削除できません');delete cities[key];select.querySelector(`option[value="${key}"]`)?.remove();select.value='tokyo';select.dispatchEvent(new Event('change'));$('gis-status').textContent='追加海域を削除しました。';}catch(e){$('gis-status').textContent=e.message;}};
 select.addEventListener('change',showCurrent);
 try{await readAreas();}catch(e){showCurrent();$('gis-status').textContent=e.message+'。既定海域を表示します。';}
}
