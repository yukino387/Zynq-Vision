import {test} from 'node:test';
import assert from 'node:assert/strict';
import {compatibility} from '../../packages/shared/src/index.js';
import {zynqManifest} from '../../apps/server/src/models/zynq-profile.js';
test('database-rounded quantization scales remain compatible, different scales and graph do not',()=>{
 const expected=zynqManifest(Buffer.from('test'));const candidate=structuredClone(expected);
 candidate.quantization.outputScales=[0.1158124968761534,0.1597768828624815];assert.deepEqual(compatibility(expected,candidate),[]);
 candidate.quantization.outputScales[1]!*=1.00001;assert.deepEqual(compatibility(expected,candidate),['quantization']);
 candidate.quantization=structuredClone(expected.quantization);candidate.quantization.inputZeroPoint=1;assert.deepEqual(compatibility(expected,candidate),['quantization']);
 candidate.quantization=structuredClone(expected.quantization);candidate.input.channels=3;assert.deepEqual(compatibility(expected,candidate),['input']);
});
