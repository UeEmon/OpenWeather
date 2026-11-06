import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readSettings,writeSettings,validLocalArea} from '../browser-settings.mjs';
test('ブラウザ設定は別ストレージに共有されない',()=>{const make=()=>{const data=new Map();return {getItem:k=>data.get(k)||null,setItem:(k,v)=>data.set(k,v)};};const a=make(),b=make();writeSettings(a,{areas:{example:{name:'私の海域'}},window:'36'});writeSettings(a,{selected:'example'});assert.equal(readSettings(a).window,'36');assert.equal(readSettings(a).areas.example.name,'私の海域');assert.deepEqual(readSettings(b),{});});
test('破損したブラウザ設定と不正な範囲を扱う',()=>{assert.deepEqual(readSettings({getItem:()=>'{broken'}),{});assert.equal(validLocalArea({name:'海域',bounds:{south:34,north:35,west:139,east:140}}),true);assert.equal(Boolean(validLocalArea({name:'海域',bounds:{south:35,north:34,west:139,east:140}})),false);});
