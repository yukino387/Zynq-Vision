"""Time existing generated RTL with ideal, nonblocking input/output stubs."""
from pathlib import Path
import json
import re
import shutil

root = Path(__file__).resolve().parents[2]
test = Path(__file__).resolve().parent
build = test / 'build/rtl'
build.mkdir(parents=True, exist_ok=True)
rtl = root / 'temporary/micro_io_test/build/d/hls/syn/verilog'
modules = {}
for p in rtl.glob('*.v'):
    for name in re.findall(r'\bmodule\s+(\w+)', p.read_text()):
        modules[name] = p
selected = {
    'input': 'conv_load_input_plane_0u_s',
    'weight': 'conv_load_weight_lane_0u_s',
    'quant': 'conv_quantize_output',
    'compute': 'conv_compute',
    'inputs': 'conv_load_input',
    'store': 'conv_store_output',
}
pending = list(selected.values())
dependencies = set()
while pending:
    name = pending.pop()
    if name in dependencies:
        continue
    dependencies.add(name)
    source = modules[name].read_text()
    pending.extend((set(re.findall(r'\b\w+\b', source)) & modules.keys()) - dependencies)
for p in rtl.glob('*.dat'):
    shutil.copy2(p, build / p.name)

lines = ['`timescale 1ns/1ps', 'module tb;',
         'reg clk=0; always #4 clk=~clk;',
         'reg rst=1,start=0;',
         'reg [31:0] sz=14,rr=0,cc=0,st=1,kk=3,co=48,ci=512,ce=0,cr=0;',
         'wire [3:0] tile=sz==7?7:14;',
         'wire [4:0] cols=((st==2?sz/2:sz)-cc)<16?((st==2?sz/2:sz)-cc):16;',
         'wire [9:0] bytes=(st==2?sz/2:sz)==7?8:16;',
         'integer cycle=0; always @(posedge clk) cycle<=cycle+1;',
         'integer input_writes=0,quant_words=0,errors=0;',
         'integer i_done=-1,w_done=-1,q_done=-1,c_done=-1,started;',
         'integer ins_done=-1,s_done=-1;',
         'reg checking=0;']
for label, name in selected.items():
    lines.append(f'reg {label}_start=0;')
    source = modules[name].read_text()
    ports = re.findall(r'^(input|output)\s+(\[[^\]]+\]\s+)?(\w+)\s*;', source, re.M)
    connections = []
    inputs = []
    for direction, width, port in ports:
        if direction == 'output':
            signal = label + '_' + port
            lines.append(f'wire {width}{signal};')
            connections.append(f'.{port}({signal})')
            continue
        inputs.append(port)
        expression = "'0"
        if port == 'ap_clk': expression = 'clk'
        elif port == 'ap_rst': expression = 'rst'
        elif port == 'ap_start': expression = label + '_start'
        elif port in ['ap_continue', 'enabled', 'start_full_n'] or port.endswith(('_full_n', '_ap_vld')): expression = "1'b1"
        elif port.endswith('_fifo_cap'): expression = "'1"
        elif port.startswith('m_axi_'):
            if port.endswith(('AWREADY', 'WREADY', 'ARREADY', 'RVALID', 'RLAST', 'BVALID')): expression = "1'b1"
            elif port.endswith('RFIFONUM'): expression = "11'd2047"
            elif port.endswith('RDATA'): expression = "64'h0101010101010101" if label in ['input', 'inputs'] else "64'd0"
        elif port in ['quant_s_q0', 'quant_s_q1', 'quant_ns_q0', 'quant_ns_q1']: expression = "6'd1"
        elif port in ['quant_m_q0', 'quant_m_q1', 'quant_nm_q0', 'quant_nm_q1']: expression = "32'd1"
        elif port.startswith('buffer_') and port.endswith('_q0'): expression = "32'd16"
        elif port in ['size']: expression = 'sz[8:0]'
        elif port == 'row': expression = 'rr[15:0]'
        elif port == 'col': expression = 'cc[15:0]'
        elif port == 'stride': expression = 'st[1:0]'
        elif port == 'kernel': expression = 'kk[1:0]'
        elif port in ['channels', 'ci']: expression = 'ci[9:0]'
        elif port == 'co': expression = 'co[9:0]'
        elif port == 'cache_enabled': expression = 'ce[0]'
        elif port == 'cache_reuse': expression = 'cr[0]'
        elif port in ['tile', 'p_read']: expression = 'tile'
        elif port in ['cols', 'p_read1']: expression = 'cols'
        elif port == 'p_read2': expression = 'bytes'
        connections.append(f'.{port}({expression})')
    lines.append(name + ' ' + label + '_dut(\n' + ',\n'.join(connections) + '\n);')
    lines.append(f'always @(posedge clk) if({label}_ap_ready) {label}_start<=0;')

lines += [r'''
always @(posedge clk) if(checking) begin
    if(input_ap_done && i_done<0) i_done=cycle-started;
    if(weight_ap_done && w_done<0) w_done=cycle-started;
    if(quant_ap_done && q_done<0) q_done=cycle-started;
    if(compute_ap_done && c_done<0) c_done=cycle-started;
    if(inputs_ap_done && ins_done<0) ins_done=cycle-started;
    if(store_ap_done && s_done<0) s_done=cycle-started;
    if(input_plane_ce0 && input_plane_we0) begin
        input_writes=input_writes+1;
        if(input_plane_d0 !== 0 && input_plane_d0 !== 1) errors=errors+1;
    end
    if(quant_words_0_write) quant_words=quant_words+1;
    if(quant_words_1_write) quant_words=quant_words+1;
    if(quant_words_2_write) quant_words=quant_words+1;
    if(quant_words_3_write) quant_words=quant_words+1;
end

task probe(input integer id,ss,stride_v,kernel_v,channels_v,outputs_v,row_v,col_v,cache_v,reuse_v);
integer expected_input,expected_words,height,width,out_size;
begin
    @(negedge clk); checking=0; rst=1; start=0;
    sz=ss;st=stride_v;kk=kernel_v;ci=channels_v;co=outputs_v;
    rr=row_v;cc=col_v;ce=cache_v;cr=reuse_v;
    repeat(8) @(negedge clk);
    rst=0; repeat(2) @(negedge clk);
    input_writes=0;quant_words=0;i_done=-1;w_done=-1;q_done=-1;c_done=-1;ins_done=-1;s_done=-1;
    started=cycle;checking=1;start=1;
    input_start=1;weight_start=1;quant_start=1;compute_start=1;inputs_start=1;store_start=1;
    @(negedge clk);start=0;
    wait(i_done>=0 && w_done>=0 && q_done>=0 && c_done>=0 && ins_done>=0 && s_done>=0);
    @(negedge clk);checking=0;
    out_size=stride_v==2?ss/2:ss;
    height=(out_size==7?6:13)*stride_v+kernel_v;
    width=((out_size-col_v<16?out_size-col_v:16)-1)*stride_v+kernel_v;
    expected_input=height*width;
    expected_words=outputs_v*(out_size==7?7:14)*(out_size==7?8:16)/8;
    if(input_writes!=expected_input || quant_words!=expected_words) begin
        $display("CHECK FAIL id=%0d input=%0d/%0d quant=%0d/%0d",id,input_writes,expected_input,quant_words,expected_words);
        errors=errors+1;
    end
    $display("PROBE %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d %0d",id,i_done,w_done,q_done,c_done,input_writes,quant_words,ss,kernel_v,outputs_v,ins_done,s_done);
end
endtask
initial begin
''']
cases = [
    # size, stride, kernel, input channels, output channels (<=48), row, col, cache, reuse
    [224,2,3,1,32,0,0,1,0], [224,2,3,1,32,14,16,1,1],
    [56,1,1,64,48,0,0,1,0], [56,1,1,64,48,14,16,1,1],
    [28,1,1,128,48,0,0,1,0], [28,1,1,128,48,14,16,1,1],
    [14,1,1,256,48,0,0,0,0], [7,1,1,512,48,0,0,0,0],
    [14,1,3,256,48,0,0,0,0], [7,1,3,512,48,0,0,0,0],
    [56,1,3,64,48,0,0,1,0], [56,1,3,64,48,14,16,1,1],
    [7,1,3,512,4,0,0,0,0], [14,1,3,256,4,0,0,0,0],
]
for i, case in enumerate(cases):
    lines.append('probe(' + ','.join(map(str, [i] + case)) + ');')
lines += ['if(errors) $fatal(1,"OFFLINE RTL CHECK FAIL errors=%0d",errors);',
          '$display("OFFLINE RTL PASS"); $finish; end',
          'initial begin #1000000; $display("DONE STATE %0d %0d %0d %0d %0d %0d",i_done,w_done,q_done,c_done,ins_done,s_done); $fatal(1,"TIMEOUT"); end', 'endmodule']
(build / 'tb.sv').write_text('\n'.join(lines) + '\n')
(build / 'cases.json').write_text(json.dumps(cases))
(build / 'sources.prj').write_text('\n'.join('verilog work "' + p.as_posix() + '"' for p in sorted({modules[n] for n in dependencies})) + '\nsv work "tb.sv"\n')
(build / 'run.tcl').write_text('run all\nquit\n')
print(json.dumps({'modules': len(dependencies), 'cases': len(cases), 'build': str(build)}))
