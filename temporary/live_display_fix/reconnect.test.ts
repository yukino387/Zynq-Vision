import {test} from 'node:test';
import assert from 'node:assert/strict';
import dgram from 'node:dgram';
import {ZynqUdpTransport} from '../../apps/server/src/devices/zynq.js';
const waitFor=async(check:()=>boolean)=>{const end=Date.now()+4500;while(!check()){if(Date.now()>end)throw new Error('Expected heartbeat recovery');await new Promise(r=>setTimeout(r,20));}};
test('board restart re-registers lost image stream; a paused stream stays paused',async()=>{
 const peer=dgram.createSocket('udp4');await new Promise<void>(resolve=>peer.bind(0,'127.0.0.1',resolve));
 const transport=new ZynqUdpTransport('127.0.0.1',peer.address().port,0);
 let flags=5,hellos=0,polls=0,modelReads=0;
 peer.on('message',(packet,remote)=>{
  const id=packet.readUInt32LE(4);
  if(packet.readUInt32LE(0)===0x314c444d){modelReads++;const reply=Buffer.alloc(124);reply.writeUInt32LE(0x3152444d);reply.writeUInt32LE(id,4);reply.writeUInt32LE(11,24);reply.write('sd-model',28);peer.send(reply,remote.port,remote.address);return;}
  const command=packet.readUInt32LE(8);if(command===1){hellos++;flags=5;}if(command===0)polls++;
  const reply=Buffer.alloc(48);reply.writeUInt32LE(0x31545343);reply.writeUInt32LE(id,4);reply.writeUInt32LE(0x7020,8);reply.writeUInt32LE(flags,12);peer.send(reply,remote.port,remote.address);
 });
 try{await transport.connect();assert.equal(hellos,1);flags=4;await waitFor(()=>polls>0);assert.equal(hellos,1,'pause must not trigger a new HELLO');assert.equal(transport.getStatus().runtimeState,'READY');flags=1;await waitFor(()=>hellos===2&&modelReads===2);assert.equal(transport.getStatus().runtimeState,'RUNNING');assert.equal(transport.getCurrentModel(),'sd-model');}finally{await transport.disconnect();peer.close();}
});
