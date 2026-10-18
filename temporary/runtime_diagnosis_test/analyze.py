from pathlib import Path
import struct
import json
import re
import csv
import hashlib

root = Path(__file__).resolve().parents[2]
test = Path(__file__).resolve().parent
build = test / 'build'
profile = json.loads((root / 'temporary/micro_io_test/build/comparison.json').read_text())
commands = struct.unpack('<330i', (root / 'camera/int8/metadata.bin').read_bytes()[:1320])
clock = 125
pitches = {7:8,14:16,28:32,56:64,112:128,224:256}
rows = []
groups = {}
for i, layer in enumerate(profile['layers']):
    ci,co,size,stride,kernel,act = commands[i*10+4:i*10+10]
    elapsed = layer['candidate_us']
    groups[kernel] = groups.get(kernel,0) + elapsed
    if kernel not in [1,3]:
        continue
    out = size // stride
    padded = ((ci+7)//8*8) * ((co+47)//48*48) * out*out*kernel*kernel
    logical = ci*co*out*out*kernel*kernel
    quant_iterations = ((co+3)//4)*out*pitches[out]
    tiles = ((out+13)//14)*((out+15)//16)*((co+47)//48)
    # Each output channel and logical row starts a separate write for every
    # column tile when out>14. Small output planes are written in one burst.
    write_requests = co if out<=14 else co*out*((out+15)//16)
    input_requests = input_words = 0
    tile_rows = 7 if out==7 else 14
    output_groups = (co+47)//48
    for r in range(0,out,tile_rows):
        for c in range(0,out,16):
            cols=min(16,out-c)
            height=(tile_rows-1)*stride+kernel
            width=(cols-1)*stride+kernel
            pad=1 if kernel==3 else 0
            first=1 if c==0 and pad else 0
            x=c*stride-pad
            last=min(width,size-x)
            start=x+first
            words=((start&7)+last-first+7)//8
            valid_rows=sum(0<=r*stride-pad+y<size for y in range(height))
            input_requests+=valid_rows*ci*output_groups
            input_words+=valid_rows*ci*output_groups*words
    cache=out>14 and (kernel==1 or ci<=128)
    weight_reads=output_groups*((ci+7)//8)*4*(1 if cache else ((out+tile_rows-1)//tile_rows)*((out+15)//16))
    weight_bytes=weight_reads*96*kernel*kernel
    rows.append(dict(index=i,name=layer['layer'],ci=ci,co=co,size=size,stride=stride,kernel=kernel,
                     board_us=elapsed,logical_mac=logical,padded_mac=padded,
                     ideal_mac_us=padded/384/clock,quant_loop_payload_us=quant_iterations/clock,
                     output_tiles=tiles,output_bytes=co*out*pitches[out],write_requests=write_requests,
                     input_read_requests=input_requests,input_bytes=input_words*8,
                     weight_read_requests=weight_reads,weight_bytes=weight_bytes))

probe_log = (build / 'rtl/simulation.log').read_text()
assert 'OFFLINE RTL PASS' in probe_log
probe_cases = json.loads((build / 'rtl/cases.json').read_text())
probes = []
for match in re.finditer(r'^PROBE (.*)$', probe_log, re.M):
    values = list(map(int,match.group(1).split()))
    labels = ['id','one_input_plane_cycles','one_weight_lane_cycles','quant_cycles','compute_cycles',
              'input_plane_writes','quant_words','size','kernel','co','all_input_cycles','store_cycles']
    row = dict(zip(labels,values))
    row['configuration'] = probe_cases[row['id']]
    probes.append(row)
assert len(probes) == len(probe_cases)

full_log = (build / 'full_rtl/simulation.log').read_text()
assert 'WHOLE CONV RTL PASS' in full_log
measured = {}
for match in re.finditer(r'^LAYER (.*)$', full_log, re.M):
    i,total,load,store,bias,compute,inputs,weights = map(int,match.group(1).split())
    measured[i] = dict(rtl_cycles=total,load_region_cycles=load,store_region_cycles=store,
                       bias_region_cycles=bias,compute_active_cycles=compute,
                       input_active_cycles=inputs,weight_active_cycles=weights)
assert len(measured) == len(rows)
for row in rows:
    row.update(measured[row['index']])
    row['ideal_interface_rtl_us'] = row['rtl_cycles']/clock
    row['board_minus_ideal_interface_us'] = row['board_us']-row['ideal_interface_rtl_us']
    # Input/weight/compute are concurrent. Never sum these as frame elapsed.
    row['other_control_cycles'] = row['rtl_cycles']-row['load_region_cycles']-row['store_region_cycles']-row['bias_region_cycles']
    assert row['other_control_cycles'] >= 0

setup = struct.unpack('<99I',(root/'temporary/micro_io_test/build/board/setup_us.bin').read_bytes())
summary = dict(
    reference_commit='de2d083', clock_mhz=clock,
    source_sha256=hashlib.sha256((root/'hardware/hls/src/std_conv.cpp').read_bytes()).hexdigest(),
    formal_source_modified=False,board_connected=False,new_board_test_performed=False,
    reference_forward_us=profile['candidate_forward_us'],
    reference_setup_us=[sum(setup[i:i+33]) for i in range(0,99,33)],
    reference_operator_us=groups,
    padded_mac=sum(row['padded_mac'] for row in rows),
    ideal_mac_us=sum(row['ideal_mac_us'] for row in rows),
    conv_board_us=sum(row['board_us'] for row in rows),
    conv_ideal_interface_rtl_us=sum(row['ideal_interface_rtl_us'] for row in rows),
    rtl_serial_regions_us={label:sum(row[key] for row in rows)/clock for label,key in
        [('load_compute','load_region_cycles'),('store_output','store_region_cycles'),
         ('bias_initialization','bias_region_cycles'),('other_control','other_control_cycles')]},
    concurrent_activity_us={label:sum(row[key] for row in rows)/clock for label,key in
        [('compute','compute_active_cycles'),('input','input_active_cycles'),('weight','weight_active_cycles')]},
    output_write_requests=sum(row['write_requests'] for row in rows),
    output_bytes=sum(row['output_bytes'] for row in rows),
    input_read_requests=sum(row['input_read_requests'] for row in rows),
    input_bytes=sum(row['input_bytes'] for row in rows),
    weight_read_requests=sum(row['weight_read_requests'] for row in rows),
    weight_bytes=sum(row['weight_bytes'] for row in rows),
    limitations=[
        'Submodule and whole-convolution RTL use always-ready internal HLS memory-interface stubs.',
        'AXI adapters, interconnect, physical DDR and camera competition are not simulated.',
        'Difference from previous board measurements is not a direct DDR stall counter.',
        'Functional full-model correctness comes from the previous board test; this is a timing experiment.',
        'Input, weight and compute activity overlap and must not be added as elapsed time.',
        'Module active cycles include their internal pipeline/control overhead; they are not DSP utilization counters.',
        'Read/write request counts are derived from source loops; they are not measured DDR-controller transactions.',
    ],
    probes=probes,layers=rows,
)
(build/'diagnosis.json').write_text(json.dumps(summary,indent=2)+'\n')
with (build/'layers.csv').open('w',newline='',encoding='utf-8-sig') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
print(json.dumps({k:v for k,v in summary.items() if k not in ['probes','layers','limitations']},indent=2))
print('TOP GAPS',[(r['name'],round(r['board_minus_ideal_interface_us'],2)) for r in sorted(rows,key=lambda r:r['board_minus_ideal_interface_us'],reverse=True)[:6]])
