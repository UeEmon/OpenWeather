import {cities,describe,forecastURL,validate,marineURL} from './weather.mjs';
const $=id=>document.getElementById(id);
const num=x=>Number.isFinite(x)?Math.round(x):'—';
const weekday=s=>new Intl.DateTimeFormat('ja-JP',{month:'numeric',day:'numeric',weekday:'short',timeZone:'Asia/Tokyo'}).format(new Date(`${s}T12:00:00+09:00`));
let controller;
function clear(){for(const id of ['temperature','feels','high','low','humidity','wind','rain','sunset'])$(id).textContent='—';$('hours').replaceChildren();$('days').replaceChildren();$('condition').textContent='天気を取得しています';$('updated').textContent='Open-Meteo の公開データを使用';$('hero-icon').textContent='☁';}
function render(d){const c=d.current, daily=d.daily,h=d.hourly;
 $('temperature').textContent=num(c.temperature_2m);$('feels').textContent=num(c.apparent_temperature);$('high').textContent=num(daily.temperature_2m_max[0]);$('low').textContent=num(daily.temperature_2m_min[0]);
 const [icon,label]=describe(c.weather_code,!!c.is_day);$('condition').textContent=label;$('hero-icon').textContent=icon;
 $('humidity').textContent=`${num(c.relative_humidity_2m)} %`;$('wind').textContent=`${Number.isFinite(c.wind_speed_10m)?c.wind_speed_10m.toFixed(1):'—'} m/s`;$('rain').textContent=`${Number.isFinite(c.precipitation)?c.precipitation:'—'} mm`;$('sunset').textContent=daily.sunset[0]?.slice(11,16)||'—';
 $('updated').textContent=`データ時刻 ${c.time.replace('T',' ')} JST · モデル推定値`;
 const first=h.time.findIndex(t=>t>=c.time.slice(0,13)+':00');
 h.time.slice(Math.max(0,first),Math.max(0,first)+24).forEach((t,k)=>{const i=Math.max(0,first)+k;const el=document.createElement('div');el.className='hour';const [ic,desc]=describe(h.weather_code[i],!!h.is_day[i]);el.innerHTML=`<time></time><span class="weather-icon"></span><strong></strong><small></small>`;el.querySelector('time').textContent=t.slice(11,16);el.querySelector('time').dateTime=t+'+09:00';el.querySelector('span').textContent=ic;el.querySelector('span').title=desc;el.querySelector('strong').textContent=num(h.temperature_2m[i])+'°';el.querySelector('small').textContent='☂ '+num(h.precipitation_probability[i])+'%';$('hours').append(el);});
 daily.time.forEach((t,i)=>{const el=document.createElement('div');el.className='day';el.innerHTML='<span class="day-label"></span><span class="weather-icon"></span><span class="precip"></span><span class="range"><span></span><i></i></span><strong></strong>';el.querySelector('.day-label').textContent=i===0?'今日':weekday(t);const [ic,desc]=describe(daily.weather_code[i]);el.querySelector('.weather-icon').textContent=ic;el.querySelector('.weather-icon').title=desc;el.querySelector('.precip').textContent=num(daily.precipitation_probability_max[i])+'%';el.querySelector('.range span').textContent=num(daily.temperature_2m_min[i])+'°';el.querySelector('strong').textContent=num(daily.temperature_2m_max[i])+'°';$('days').append(el);});
}
async function loadMarine(city,own){
 for(const id of ['wave','period','direction','sea-temp'])$(id).textContent='—';
 $('marine-hours').replaceChildren();$('marine-status').textContent='海象データを取得しています';$('coordinates').textContent=`北緯 ${city.lat.toFixed(2)}° / 東経 ${city.lon.toFixed(2)}°`;
 try{const response=await fetch(marineURL(city),{signal:own.signal});if(!response.ok)throw Error('marine API');const d=await response.json();if(controller!==own)return;const c=d.current;if(!c||!Number.isFinite(c.wave_height))throw Error('no marine data');
 const set=(id,v,digits)=>$(id).textContent=Number.isFinite(v)?v.toFixed(digits):'—';
 set('wave',c.wave_height,1);set('period',c.wave_period,1);set('direction',c.wave_direction,0);set('sea-temp',c.sea_surface_temperature,1);
 $('marine-status').textContent=`データ時刻 ${c.time.replace('T',' ')} JST · 海洋モデル推定値（観測値ではありません）`;
 const h=d.hourly;if(!h?.time)return;const start=Math.max(0,h.time.findIndex(t=>t>=c.time.slice(0,13)+':00'));
 h.time.slice(start,start+24).forEach((t,k)=>{const i=start+k;const el=document.createElement('div');el.className='hour marine-hour';const time=document.createElement('time');time.textContent=t.slice(11,16);const value=document.createElement('strong');value.textContent=Number.isFinite(h.wave_height[i])?h.wave_height[i].toFixed(1)+' m':'—';const sub=document.createElement('small');sub.textContent=`周期 ${Number.isFinite(h.wave_period[i])?h.wave_period[i].toFixed(1):'—'} 秒`;el.append(time,value,sub);$('marine-hours').append(el);});
 }catch(e){if(controller===own)$('marine-status').textContent='海象データを取得できませんでした。「更新」で再試行できます。';}
}
async function load(){controller?.abort();const own=new AbortController();controller=own;clear();$('status').textContent='';$('refresh').disabled=true;$('refresh').textContent='取得中…';const city=cities[$('city').value];$('place').textContent=city.name;const timeout=setTimeout(()=>own.abort(),15000);const marineTask=loadMarine(city,own);
 try{const res=await fetch(forecastURL(city),{signal:own.signal});if(!res.ok)throw Error(`HTTP ${res.status}`);const d=validate(await res.json());if(controller!==own)return;render(d);}catch(e){if(controller!==own)return;$('condition').textContent='天気を取得できませんでした';$('status').textContent='予報に接続できませんでした。インターネット接続を確認して、もう一度お試しください。';const b=document.createElement('button');b.textContent='再試行';b.className='outline';b.onclick=load;$('status').append(b);}finally{await marineTask;clearTimeout(timeout);if(controller===own){$('refresh').disabled=false;$('refresh').textContent='↻ 更新';}}}
try{const saved=localStorage.getItem('umibiyori-area');if(cities[saved])$('city').value=saved;}catch{}
$('date').textContent=new Intl.DateTimeFormat('ja-JP',{dateStyle:'full',timeZone:'Asia/Tokyo'}).format(new Date())+' · 日本時間';
$('city').addEventListener('change',()=>{try{localStorage.setItem('umibiyori-area',$('city').value);}catch{}load();});$('refresh').addEventListener('click',load);load();
