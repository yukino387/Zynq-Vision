from pathlib import Path
import struct,json,statistics
root=Path(__file__).resolve().parents[2]
test=Path(__file__).resolve().parent
raw=struct.unpack('<1188I',(test/'build/live_counters.bin').read_bytes())
fields=json.loads((test/'counters.json').read_text())
layers=json.loads((root/'temporary/int8_rebuild_test/build/command_names.json').read_text())
commands=struct.unpack('<330i',(root/'camera/int8/metadata.bin').read_bytes()[:1320])
rows=[]
for layer,label in enumerate(layers):
    samples=[raw[(phase*33+layer)*2:(phase*33+layer+1)*2] for phase in range(18)]
    assert samples[0][0]==samples[0][1],(label,samples[0])
    assert all(total>0 for total,value in samples),(label,samples)
    c=[value for total,value in samples]
    c[0]=statistics.median(total for total,value in samples)
    row={'layer':label,'operator':{0:'upsample',1:'conv1',2:'pool',3:'conv3',5:'requant'}[commands[layer*10+8]]}
    row.update({name+'_us':value/125 for name,value in zip(fields,c) if name not in ['read_beats','write_beats']})
    row['read_bytes']=c[11]*8;row['write_bytes']=c[12]*8
    rows.append(row)
summary={k:sum(row[k] for row in rows) for k in rows[0] if k not in ['layer','operator']}
cpu_values=struct.unpack('<9I',(test/'build/live_cpu.bin').read_bytes())
cpu=dict(zip(['camera_begin_us','input_copy_us','gray_horizontal_us','gray_vertical_us','register_setup_us','head_copy_us','counter_readback_us','input_flush_us','camera_finish_us'],cpu_values))
result={'clock_mhz':125,'sampling':'selected phase rotates once per frame; last 18 phase samples',
        'summary':summary,'cpu':cpu,'layers':rows,
        'operator_totals_us':{kind:sum(row['total_us'] for row in rows if row['operator']==kind) for kind in ['conv3','conv1','pool','upsample','requant']}}
(test/'build/live_results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'summary':summary,'cpu':cpu,'operators':result['operator_totals_us']},indent=2))
