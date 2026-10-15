from pathlib import Path
import argparse,json,re,shutil

parser=argparse.ArgumentParser()
parser.add_argument('version',choices=['baseline','candidate'])
args=parser.parse_args()
test=Path(__file__).resolve().parent
root=test.parents[1]
rtl=(root/'temporary/micro_io_test/build/d/hls/syn/verilog' if args.version=='baseline'
     else test/'build/candidate/hls/syn/verilog')
build=test/'build'/('rtl_'+args.version)
build.mkdir(parents=True,exist_ok=True)
modules={}
for p in rtl.glob('*.v'):
    for name in re.findall(r'\bmodule\s+(\w+)',p.read_text()): modules[name]=p
pending=['conv_load_input']; dependencies=set()
while pending:
    name=pending.pop()
    if name in dependencies:continue
    dependencies.add(name)
    pending.extend((set(re.findall(r'\b\w+\b',modules[name].read_text()))&modules.keys())-dependencies)
for p in rtl.glob('*.dat'):shutil.copy2(p,build/p.name)
lines=['`timescale 1ns/1ps','module tb;',
       'reg clk=0;always #4 clk=~clk;', 'reg rst=1,start=0,checking=0;',
       'reg [31:0] sz,st,kk,ci,nn,rr,cc;',
       'integer cycle=0,begun,writes=0,requests=0,errors=0;',
       'always @(posedge clk) cycle<=cycle+1;',
       'integer y,x,sy,sx;reg [7:0] expected;']
ports=re.findall(r'^(input|output)\s+(\[[^\]]+\]\s+)?(\w+)\s*;',modules['conv_load_input'].read_text(),re.M)
connections=[];widths={}
for direction,width,port in ports:
    if direction=='output':
        lines.append(f'wire {width}{port};');connections.append(f'.{port}({port})');continue
    expression="'0"
    if port=='ap_clk':expression='clk'
    elif port=='ap_rst':expression='rst'
    elif port=='ap_start':expression='start'
    elif port=='ap_continue' or port.endswith('_ap_vld'):expression="1'b1"
    elif port=='n_val':expression='nn[9:0]'
    elif port=='ci':expression='ci[9:0]'
    elif port=='size':expression='sz[8:0]'
    elif port=='row':expression='rr[8:0]'
    elif port=='col':expression='cc[8:0]'
    elif port=='stride':expression='st[1:0]'
    elif port=='kernel':expression='kk[1:0]'
    elif port.startswith('m_axi_'):
        if port.endswith(('AWREADY','WREADY','ARREADY','RVALID','RLAST','BVALID')):expression="1'b1"
        elif port.endswith('RFIFONUM'):expression="11'd2047"
        elif port.endswith('RDATA'):expression="64'h0101010101010101"
    connections.append(f'.{port}({expression})')
lines.append('conv_load_input dut(\n'+',\n'.join(connections)+'\n);')
lines.append('always @(posedge clk) if(ap_ready) start<=0;')
lines.append('always @(posedge clk) if(checking) begin')
for lane in range(8):
    for port in [0,1]:
        prefix=f'next_input_{lane}'
        if not any(name==prefix+f'_we{port}' for _,_,name in ports):continue
        lines.append(f'''if({prefix}_ce{port} && {prefix}_we{port}) begin
            writes=writes+1;
            y={prefix}_address{port}/33;x={prefix}_address{port}%33;
            sy=rr*st+y-(kk==3);sx=cc*st+x-(kk==3);
            expected=(nn+{lane}<ci && sy>=0 && sy<sz && sx>=0 && sx<sz)?1:0;
            if({prefix}_d{port} !== expected) begin errors=errors+1;$display("DATA FAIL lane={lane} y=%0d x=%0d got=%0d expected=%0d",y,x,{prefix}_d{port},expected);end
        end''')
for lane in range(1,5):
    lines.append(f'if(m_axi_FM{lane}_0_ARVALID) requests=requests+1;')
lines+=['end',r'''
task probe(input integer id,ss,stride_v,kernel_v,channels_v,n_v,row_v,col_v);
integer out_size,rows,cols,expected_writes,total;
begin
    @(negedge clk);checking=0;rst=1;start=0;
    sz=ss;st=stride_v;kk=kernel_v;ci=channels_v;nn=n_v;rr=row_v;cc=col_v;
    repeat(8) @(negedge clk);rst=0;repeat(2) @(negedge clk);
    writes=0;requests=0;begun=cycle;checking=1;start=1;
    @(negedge clk);while(!ap_done) @(negedge clk);
    total=cycle-begun;@(negedge clk);checking=0;
    out_size=ss/stride_v;rows=out_size==7?7:14;cols=out_size-col_v<16?out_size-col_v:16;
    expected_writes=n_v>=channels_v?0:8*((rows-1)*stride_v+kernel_v)*((cols-1)*stride_v+kernel_v);
    if(writes!=expected_writes)begin errors=errors+1;$display("COUNT FAIL id=%0d writes=%0d expected=%0d",id,writes,expected_writes);end
    $display("INPUT %0d %0d %0d %0d",id,total,requests,writes);
end
endtask
initial begin
''']
cases=[[224,2,3,1,0,0,0],[224,2,3,1,0,14,16],
       [224,2,3,3,0,98,96],[112,2,3,32,8,42,48],
       [56,1,1,64,0,0,0],[56,1,1,64,0,42,48],
       [28,1,1,128,0,14,16],[14,1,1,256,0,0,0],
       [7,1,1,512,0,0,0],[14,1,3,256,0,0,0],
       [7,1,3,512,0,0,0],[14,2,3,5,0,0,0],
       [14,1,3,17,16,0,0],[7,1,1,8,8,0,0],
       [56,1,3,64,0,14,16],[28,1,3,128,0,14,16]]
for i,c in enumerate(cases):lines.append('probe('+','.join(map(str,[i]+c))+');')
lines+=['if(errors)$fatal(1,"INPUT RTL FAIL errors=%0d",errors);',
        '$display("INPUT RTL PASS");$finish;end',
        'initial begin #1000000;$fatal(1,"TIMEOUT");end','endmodule']
(build/'tb.sv').write_text('\n'.join(lines)+'\n')
(build/'cases.json').write_text(json.dumps(cases))
(build/'sources.prj').write_text('\n'.join('verilog work "'+p.as_posix()+'"' for p in sorted({modules[n] for n in dependencies}))+'\nsv work "tb.sv"\n')
(build/'run.tcl').write_text('run all\nquit\n')
print(f'Prepared {args.version} input RTL test: {len(cases)} cases')
