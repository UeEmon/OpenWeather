import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import assert from 'node:assert/strict';
import {cities,describe,forecastURL,validate,marineURL} from '../weather.mjs';
test('各海域は共通APIを参照する',()=>{for(const [id,c] of Object.entries(cities)){const u=new URL(forecastURL(c),'https://weather.test');assert.equal(u.pathname,'/api/v1/weather');assert.equal(u.searchParams.get('area'),id);assert.equal(u.origin,'https://weather.test');}});
test('WMOコードを晴雨雪と夜間に分類',()=>{assert.equal(describe(0,false)[0],'☾');assert.equal(describe(65)[1],'雨');assert.equal(describe(75)[1],'雪');assert.equal(describe(95)[1],'雷雨');assert.equal(describe(999)[1],'不明');});
test('空レスポンスや不完全なデータを拒否',()=>{for(const d of [null,{}, {current:{temperature_2m:null}}])assert.throws(()=>validate(d));const d={current:{temperature_2m:20},hourly:{time:Array(168).fill('')},daily:{time:Array(7).fill('')}};assert.equal(validate(d),d);});

test('海象APIも同一オリジンの共通APIを使う',()=>{const u=new URL(marineURL(cities.tokyo),'https://weather.test');assert.equal(u.pathname,'/api/v1/marine');assert.equal(u.searchParams.get('area'),'tokyo');});

test('Webと収集コンテナの海域定義が一致',()=>{assert.deepEqual(JSON.parse(readFileSync(new URL('../collector/areas.json',import.meta.url),'utf8')),cities);});
