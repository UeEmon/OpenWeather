import {test} from 'node:test';
import assert from 'node:assert/strict';
import {sampleBathymetry,depthColor} from '../bathymetry-gis.mjs';
const grid={latitude:[34,35],longitude:[139,140],height_m:[-100,-200,-300,-400],global:false};
test('負の海底標高を維持して双線形補間する',()=>{assert.equal(sampleBathymetry(grid,139.5,34.5),-250);assert.equal(sampleBathymetry(grid,139,34),-100);assert.equal(sampleBathymetry(grid,140.1,34.5),null);});
test('欠測値を0mの海底と偽らない',()=>{assert.equal(sampleBathymetry({...grid,height_m:[null,-2,-3,-4]},139.5,34.5),null);assert.deepEqual(depthColor(null),[0,0,0,0]);assert.deepEqual(depthColor(10),[0,0,0,0]);assert.ok(depthColor(-3000)[3]>0);});
