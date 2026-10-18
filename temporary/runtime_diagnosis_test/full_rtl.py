"""Whole-convolution timing against an ideal HLS internal memory interface.

No AXI adapters, interconnect or DDR controller are simulated. Consequently these
cycles are a diagnostic reference, not a prediction of board latency.
"""
from pathlib import Path
import re
import json
import struct
import shutil

root = Path(__file__).resolve().parents[2]
test = Path(__file__).resolve().parent
build = test / 'build/full_rtl'
build.mkdir(parents=True, exist_ok=True)
rtl = root / 'temporary/micro_io_test/build/d/hls/syn/verilog'
modules = {}
for p in rtl.glob('*.v'):
    for name in re.findall(r'\bmodule\s+(\w+)', p.read_text()):
        modules[name] = p
pending = ['conv_std_conv']
dependencies = set()
while pending:
    name = pending.pop()
    if name in dependencies:
        continue
    dependencies.add(name)
    pending.extend((set(re.findall(r'\b\w+\b', modules[name].read_text())) & modules.keys()) - dependencies)
for p in rtl.glob('*.dat'):
    shutil.copy2(p, build / p.name)

lines = ['`timescale 1ns/1ps', 'module tb;',
         'reg clk=0; always #4 clk=~clk;', 'reg rst=1,start=0;',
         'reg [31:0] ci,co,sz,st,kk,act;',
         'integer cycle=0; always @(posedge clk) cycle<=cycle+1;',
         'integer begun,total,load_cycles,store_cycles,bias_cycles,compute_cycles,input_cycles,weight_cycles;',
         'reg checking=0;']
ports = re.findall(r'^(input|output)\s+(\[[^\]]+\]\s+)?(\w+)\s*;', modules['conv_std_conv'].read_text(), re.M)
connections = []
for direction, width, port in ports:
    if direction == 'output':
        lines.append(f'wire {width}{port};')
        connections.append(f'.{port}({port})')
        continue
    expression = "'0"
    if port == 'ap_clk': expression = 'clk'
    elif port == 'ap_rst': expression = 'rst'
    elif port == 'ap_start': expression = 'start'
    elif port == 'ch_in': expression = 'ci[9:0]'
    elif port == 'ch_out': expression = 'co[9:0]'
    elif port == 'fm_size': expression = 'sz[8:0]'
    elif port == 'stride': expression = 'st[1:0]'
    elif port == 'kernel': expression = 'kk[1:0]'
    elif port == 'act': expression = 'act[0]'
    elif port.startswith('m_axi_'):
        if port.endswith(('AWREADY','WREADY','ARREADY','RVALID','RLAST','BVALID')): expression = "1'b1"
        elif port.endswith('RFIFONUM'): expression = "11'd2047"
        elif port.endswith('RDATA'):
            expression = "64'h0101010101010101" if '_FM' in port else "32'd1" if '_B_' in port else "64'd0"
    connections.append(f'.{port}({expression})')
lines.append('conv_std_conv dut(\n' + ',\n'.join(connections) + '\n);')

std = modules['conv_std_conv'].read_text()
load_name = re.search(r'conv_load_compute\s+(\w+)\(', std).group(1)
store_name = re.search(r'conv_store_output\s+(\w+)\(', std).group(1)
bias_name = re.search(r'conv_load_bias\s+(\w+)\(', std).group(1)
load_source = modules['conv_load_compute'].read_text()
compute_name = re.search(r'conv_compute\s+(\w+)\(', load_source).group(1)
input_name = re.search(r'conv_load_input\s+(\w+)\(', load_source).group(1)
weight_name = re.search(r'conv_load_weight\s+(\w+)\(', load_source).group(1)
paths = {'load': 'dut.'+load_name, 'store': 'dut.'+store_name, 'bias': 'dut.'+bias_name,
         'compute': 'dut.'+load_name+'.'+compute_name,
         'input': 'dut.'+load_name+'.'+input_name,
         'weight': 'dut.'+load_name+'.'+weight_name}
lines.append('always @(posedge clk) if(checking) begin')
for label, path in paths.items():
    lines.append(f'if(!{path}.ap_idle) {label}_cycles={label}_cycles+1;')
lines += ['end', r'''
task probe(input integer id,cii,coo,sizee,stridee,kernell,activation);
begin
    @(negedge clk); checking=0;rst=1;start=0;
    ci=cii;co=coo;sz=sizee;st=stridee;kk=kernell;act=activation;
    repeat(8) @(negedge clk);rst=0;
    repeat(2) @(negedge clk);
    load_cycles=0;store_cycles=0;bias_cycles=0;compute_cycles=0;input_cycles=0;weight_cycles=0;
    begun=cycle;checking=1;start=1;
    @(negedge clk); start=0;
    wait(ap_done); @(negedge clk);checking=0;total=cycle-begun;
    $display("LAYER %0d %0d %0d %0d %0d %0d %0d %0d",id,total,load_cycles,store_cycles,bias_cycles,compute_cycles,input_cycles,weight_cycles);
end
endtask
initial begin
''']
commands = struct.unpack('<330i', (root / 'camera/int8/metadata.bin').read_bytes()[:1320])
cases = []
for i in range(33):
    ci,co,size,stride,kernel,act = commands[i*10+4:i*10+10]
    if kernel in [1,3]:
        cases.append([i,ci,co,size,stride,kernel,act])
        lines.append('probe(' + ','.join(map(str,cases[-1])) + ');')
lines += ['$display("WHOLE CONV RTL PASS");$finish;end',
          'initial begin #200000000; $fatal(1,"TIMEOUT");end', 'endmodule']
(build / 'tb.sv').write_text('\n'.join(lines) + '\n')
(build / 'cases.json').write_text(json.dumps(cases))
(build / 'sources.prj').write_text('\n'.join('verilog work "' + p.as_posix() + '"' for p in sorted({modules[n] for n in dependencies})) + '\nsv work "tb.sv"\n')
(build / 'run.tcl').write_text('run all\nquit\n')
print(json.dumps({'modules':len(dependencies), 'layers':len(cases), 'build':str(build)}))
