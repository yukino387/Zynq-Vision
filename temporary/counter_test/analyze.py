from pathlib import Path
import struct,json,statistics,csv,hashlib,re
root=Path(__file__).resolve().parents[2]
test=Path(__file__).resolve().parent
build=test/'build/board'
log=(build/'result.log').read_text()
assert 'PASS:' in log and 'TEST ERROR:' not in log,log
for name,count in [('out0',1617),('out1',6468)]:
    actual=(build/(name+'.bin')).read_bytes()[:count]
    expected=(root/'temporary/int8_model_test/build/golden'/(name+'.bin')).read_bytes()
    assert actual==expected,name
    print('PASS',name,hashlib.sha256(actual).hexdigest())
names=json.loads((test/'counters.json').read_text())
layers=json.loads((root/'temporary/int8_rebuild_test/build/command_names.json').read_text())
commands=struct.unpack('<'+str(33*10)+'i',(root/'camera/int8/metadata.bin').read_bytes()[:33*10*4])
raw=struct.unpack('<'+str(18*33*2)+'I',(build/'counters.bin').read_bytes())
setup=struct.unpack('<594I',(build/'setup_us.bin').read_bytes())
readback=struct.unpack('<594I',(build/'readback_us.bin').read_bytes())
last_wall=[int(v,0) for v in re.search('LAYER_US = (.*)',log).group(1).split()]
rows=[]
for layer,label in enumerate(layers):
    samples=[raw[(phase*33+layer)*2:(phase*33+layer+1)*2] for phase in range(18)]
    assert samples[0][0]==samples[0][1],(label,samples[0])
    assert all(t>0 for t,v in samples),(label,samples)
    assert all(v<=t for i,(t,v) in enumerate(samples) if i not in [11,12]),(label,samples)
    assert abs(samples[17][0]/125-last_wall[layer])<5,(label,samples[17][0]/125,last_wall[layer])
    c=[value for total,value in samples]
    c[0]=statistics.median(total for total,value in samples)
    assert c[1]+c[2]+c[6]+c[7]<c[0]*1.02+1000,(label,c)
    row={'layer':label,'operator':{0:'upsample',1:'conv1',2:'pool',3:'conv3',5:'requant'}[commands[layer*10+8]],'setup_us':statistics.median(setup[run*33+layer] for run in range(18)),
         'readback_us':statistics.median(readback[run*33+layer] for run in range(18))}
    row.update({name+'_cycles':value for name,value in zip(names,c)})
    row.update({name+'_us':value/125 for name,value in zip(names,c) if name not in ['read_beats','write_beats']})
    row['read_bytes']=c[11]*8
    row['write_bytes']=c[12]*8
    row['unclassified_us']=max(0,c[0]-c[1]-c[2]-c[6]-c[7])/125
    row['compute_without_load_us']=(c[5]-c[10])/125
    rows.append(row)
summary={k:sum(r[k] for r in rows) for k in rows[0] if k not in ('layer','operator')}
cpu={name:[int(v,0) for v in re.search(name+' = (.*)',log).group(1).split()] for name in ['PREPROCESSING_US','HEAD_COPY_US','FORWARD_US']}
result={'cpu':cpu,'clock_mhz':125,'runs':18,'sampling':'two counters; each stage sampled on a separate identical-input forward','summary':summary,'layers':rows,
        'operator_totals_us':{kind:sum(r['total_us'] for r in rows if r['operator']==kind) for kind in ['conv3','conv1','pool','upsample','requant']},
        'definitions':{'scope':'phase counters describe convolution internals only; other operators have total/bus counters',
        'unclassified_us':'non-convolution operations plus convolution control gaps outside measured phases',
        'compute':'compute module active cycles, including pipeline startup/drain; not DSP useful MAC cycles',
        'read_response_gap':'union of ports with accepted outstanding read beats, RREADY=1 and RVALID=0; includes interconnect/controller delay',
        'read_gap_without_compute':'read_response_gap while compute module is inactive; not a causal isolated DDR stall measurement',
        'read_bytes':'accepted 64-bit AXI read beats across all eight HLS master ports; not external DDR bus traffic',
        'overlap':'input/weight loaders and compute concurrently active; nested durations must not be added'}}
(test/'build/results.json').write_text(json.dumps(result,indent=2)+'\n')
with (test/'build/layers.csv').open('w',newline='') as file:
    writer=csv.DictWriter(file,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
print(json.dumps(summary,indent=2))
for row in sorted(rows,key=lambda r:r['total_us'],reverse=True)[:8]:
    print(row['layer'],{k:round(row[k],3) for k in ['total_us','load_compute_us','compute_us','load_without_compute_us','store_us','quantize_us','write_us','read_gap_without_compute_us']})
