import {test} from 'node:test';
import assert from 'node:assert/strict';
import {hourlyIndices} from '../weather.mjs';
const now=Date.parse('2026-11-07T00:30:00+09:00');
const start=Date.parse('2026-11-06T00:00:00+09:00');
const times=Array.from({length:96},(_,i)=>new Date(start+i*3600000+9*3600000).toISOString().slice(0,16));
test('実況相当の過去12時間には未来を混ぜない',()=>{const ids=hourlyIndices(times,'history',now);assert.equal(ids.length,12);for(const i of ids){const t=Date.parse(times[i]+'+09:00');assert.ok(t>=now-12*3600000&&t<=now);}});
test('予報24時間と36時間を日付をまたいで抽出',()=>{assert.equal(hourlyIndices(times,'24',now).length,24);assert.equal(hourlyIndices(times,'36',now).length,36);});
test('欠測や未取得をゼロ埋めしない',()=>{assert.deepEqual(hourlyIndices([], 'history',now),[]);assert.equal(hourlyIndices(times.slice(24,30),'36',now).length,5);assert.throws(()=>hourlyIndices(times,'invalid',now));});
