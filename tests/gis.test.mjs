import {test} from 'node:test';
import assert from 'node:assert/strict';
import {decodeGsiHeight} from '../gis-terrain.mjs';
test('GSIの符号付き標高をメートルでデコード',()=>{assert.equal(decodeGsiHeight(0,0,100),1);assert.equal(decodeGsiHeight(255,255,156),-1);assert.equal(decodeGsiHeight(0,0,0),0);});
test('GSI欠測値と透過域は平坦な代替表示',()=>{assert.equal(decodeGsiHeight(128,0,0),0);assert.equal(decodeGsiHeight(1,1,1,0),0);});
