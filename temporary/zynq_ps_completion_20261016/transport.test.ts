import "reflect-metadata";
import { test } from "node:test";
import assert from "node:assert/strict";
import dgram from "node:dgram";
import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { ZynqUdpTransport } from "../../apps/server/src/devices/zynq.js";
import { zynqManifest } from "../../apps/server/src/models/zynq-profile.js";
test("CNC2 negotiates SD capabilities, retries acknowledged chunks and only confirms device-reported activation", async () => {
  const peer = dgram.createSocket("udp4");
  await new Promise<void>((resolve) => peer.bind(0,"127.0.0.1",resolve));
  const address=peer.address(), transport=new ZynqUdpTransport("127.0.0.1",address.port,0);
  const artifact=await readFile("camera/build/models/factory/model.bin");
  const version=artifact.subarray(24,88).toString("ascii").split("\0")[0]!;
  const expectedDigest=artifact.subarray(88,120), chunks:Buffer[]=[];
  let running=true, received=0, current="previous", generation=1, digest=Buffer.alloc(32), verified=false, dropped=false;
  peer.on("message",(packet,remote)=>{
    const id=packet.readUInt32LE(4);
    if(packet.readUInt32LE(0)===0x31434e43){
      const command=packet.readUInt32LE(8);
      if(command===1)running=true;
      if(command===2)running=!!packet.readUInt32LE(12);
      const reply=Buffer.alloc(48);reply.writeUInt32LE(0x31545343);reply.writeUInt32LE(id,4);reply.writeUInt32LE(0x7020,8);reply.writeUInt32LE(running?5:4,12);peer.send(reply,remote.port,remote.address);return;
    }
    const operation=packet.readUInt32LE(8),offset=packet.readUInt32LE(12),data=packet.subarray(20);
    const reply=Buffer.alloc(124);reply.writeUInt32LE(0x3152444d);reply.writeUInt32LE(id,4);
    if(operation===1){received=0;chunks.length=0;verified=false;}
    if(operation===2&&offset===received){chunks.push(Buffer.from(data));received+=data.length;}
    if(operation===2&&offset===1400&&!dropped){dropped=true;return;}
    if(operation===3){assert.deepEqual(Buffer.concat(chunks),artifact);verified=true;}
    if(operation===4){assert.ok(verified);current=version;digest=Buffer.from(expectedDigest);generation++;}
    reply.writeUInt32LE(received,12);reply.writeUInt32LE(artifact.length,16);reply.writeUInt32LE(generation,20);reply.writeUInt32LE(11,24);reply.write(current,28,"ascii");digest.copy(reply,92);peer.send(reply,remote.port,remote.address);
  });
  try {
    await transport.connect();
    assert.equal(transport.capabilities.modelUpdate,true);
    assert.equal(transport.capabilities.localStorage,true);
    assert.equal(transport.getCurrentModel(),"previous");
    const stages:string[]=[];
    const result=await transport.deployModel(version,zynqManifest(artifact),artifact,async(stage)=>{stages.push(stage);});
    assert.deepEqual(stages,["DOWNLOADING","VERIFYING","VERIFIED","ACTIVATING","SELF_TEST"]);
    assert.equal(result.simulated,false);assert.equal(result.selfTest,true);assert.equal(result.active,true);
    assert.equal(result.sha256,createHash("sha256").update(artifact).digest("hex"));
    assert.equal(transport.getCurrentModel(),version);assert.equal(dropped,true);
    assert.equal(transport.getStatus().reportedState.inspectionEnabled,true);
    const corrupt=Buffer.from(artifact);corrupt[200]^=1;
    await assert.rejects(()=>transport.deployModel(version,zynqManifest(corrupt),corrupt,async()=>{}),/Invalid fixed-graph/);
    assert.equal(transport.getCurrentModel(),version);
    assert.equal(received,artifact.length);
  } finally {await transport.disconnect();peer.close();}
});
