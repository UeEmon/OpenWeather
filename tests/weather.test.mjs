import {test} from 'node:test';
import assert from 'node:assert/strict';
import {cities,describe,forecastURL,validate,marineURL} from '../weather.mjs';
test('都市座標と予報リクエスト',()=>{for(const c of Object.values(cities)){const u=new URL(forecastURL(c));assert.equal(u.hostname,'api.open-meteo.com');assert.equal(u.searchParams.get('latitude'),String(c.lat));assert.equal(u.searchParams.get('timezone'),'Asia/Tokyo');assert.equal(u.searchParams.get('forecast_days'),'7');assert.equal(u.searchParams.get('wind_speed_unit'),'ms');}});
test('WMOコードを晴雨雪と夜間に分類',()=>{assert.equal(describe(0,false)[0],'☾');assert.equal(describe(65)[1],'雨');assert.equal(describe(75)[1],'雪');assert.equal(describe(95)[1],'雷雨');assert.equal(describe(999)[1],'不明');});
test('空レスポンスや不完全なデータを拒否',()=>{for(const d of [null,{}, {current:{temperature_2m:null}}])assert.throws(()=>validate(d));const d={current:{temperature_2m:20},hourly:{time:Array(168).fill('')},daily:{time:Array(7).fill('')}};assert.equal(validate(d),d);});

test('海象APIは海域座標と波予報を要求',()=>{const u=new URL(marineURL(cities.tokyo));assert.equal(u.hostname,'marine-api.open-meteo.com');assert.equal(u.searchParams.get('latitude'),'35');assert.ok(u.searchParams.get('current').includes('wave_height'));});
