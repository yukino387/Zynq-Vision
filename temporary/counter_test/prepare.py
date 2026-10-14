from pathlib import Path
import re,shutil,json
root=Path.cwd(); test=root/'temporary/counter_test'; ip=test/'build/ip'
shutil.copytree(root/'hardware/hls/build/conv/hls/impl/ip',ip,dirs_exist_ok=True)
v=ip/'hdl/verilog'
def read(name): return (v/(name+'.v')).read_text()
def save(name,s): (v/(name+'.v')).write_bytes(s.encode())
def add_output(s,name,bits):
 s,n=re.subn(r'(module\s+\w+\s*\(\s*)',r'\1'+name+',\n        ',s,count=1);assert n==1
 a=s.index(');')+2
 return s[:a]+f'\noutput [{bits-1}:0] {name};\n'+s[a:]
def idle(s,pattern):
 matches=re.findall(r'wire\s+(\w*'+pattern+r'\w*_ap_idle)\s*;',s)
 assert len(matches)==1,(pattern,matches)
 return '~'+matches[0]
def child(s,module,port,wire):
 s,n=re.subn(r'('+module+r'\s+\w+\s*\(\s*)',r'\1.'+port+'('+wire+'),\n    ',s,count=1);assert n==1,module
 return s
s=read('conv_load_compute');s=add_output(s,'prof_load',3)
s+='\n' if not s.endswith('\n') else ''
a=s.rfind('endmodule');s=s[:a]+'assign prof_load = {'+','.join(idle(s,x) for x in ['compute_U0','load_weight_U0','load_input_U0'])+'};\n'+s[a:];save('conv_load_compute',s)
s=read('conv_store_output');s=add_output(s,'prof_store',2);a=s.rfind('endmodule');s=s[:a]+'assign prof_store = {'+idle(s,'grp_write_four')+','+idle(s,'grp_store_output_Pipeline')+'};\n'+s[a:];save('conv_store_output',s)
s=read('conv_std_conv');s=add_output(s,'prof_phase',9);a=s.index(');')+2;s=s[:a]+'\nwire [2:0] prof_load;\nwire [1:0] prof_store;\n'+s[a:]
s=child(s,'conv_load_compute','prof_load','prof_load');s=child(s,'conv_store_output','prof_store','prof_store');a=s.rfind('endmodule')
expr=[idle(s,'grp_std_conv_Pipeline'),idle(s,'grp_load_bias'),'prof_load[0]','prof_load[1]','prof_load[2]',idle(s,'grp_load_compute'),idle(s,'grp_store_output'),'prof_store[0]','prof_store[1]']
s=s[:a]+'assign prof_phase = {'+','.join(reversed(expr))+'};\n'+s[a:];save('conv_std_conv',s)
s=read('conv_execute_layer');s=add_output(s,'prof_phase',9);a=s.index(');')+2;s=s[:a]+'\nwire [8:0] prof_conv;\n'+s[a:];s=child(s,'conv_std_conv','prof_phase','prof_conv');a=s.rfind('endmodule');s=s[:a]+'assign prof_phase = '+idle(s,'grp_std_conv')+" ? prof_conv : 9'b0;\n"+s[a:];save('conv_execute_layer',s)
s=read('conv');a=s.index(');')+2;s=s[:a]+'\nwire [8:0] prof_phase;\nreg [21:0] prof_total, prof_selected;\nwire [4:0] prof_select;\nreg [3:0] prof_increment;\n'+s[a:];s=child(s,'conv_execute_layer','prof_phase','prof_phase')
# The parameterized AXI slave instance has a distinct instance name.
s,n=re.subn(r'(\)\s+\w*CTRL\w*\s*\(\s*)',r'\1.prof_total(prof_total),\n    .prof_selected(prof_selected),\n    .prof_select(prof_select),\n    ',s,count=1);assert n==1
ports=['FM1','FM2','FM3','FM4','W1','W2','W3','W4']
readbeats=' + '.join("{3'b0,(m_axi_"+p+'_RVALID && m_axi_'+p+'_RREADY)}' for p in ports)
writebeats=' + '.join("{2'b0,(m_axi_"+p+'_WVALID && m_axi_'+p+'_WREADY)}' for p in ports[:4])
rstall=' || '.join('(m_axi_'+p+'_RVALID && !m_axi_'+p+'_RREADY)' for p in ports)
wstall=' || '.join('(m_axi_'+p+'_WVALID && !m_axi_'+p+'_WREADY)' for p in ports[:4])
gap=' || '.join('(prof_pending_'+p+' != 0 && m_axi_'+p+'_RREADY && !m_axi_'+p+'_RVALID)' for p in ports)
adds=['1']+['prof_phase[%d]'%i for i in range(9)]+['prof_phase[4] && (prof_phase[2] || prof_phase[3])',readbeats,writebeats,rstall,wstall,'(prof_phase[2] || prof_phase[3]) && !prof_phase[4]',gap,'('+gap+') && !prof_phase[4]']
pending=''
for port in ports:
 pending+=f"\nreg [11:0] prof_pending_{port};\nalways @(posedge ap_clk) begin\n if(!ap_rst_n || (ap_CS_fsm_state1 && ap_start)) prof_pending_{port} <= 0;\n else prof_pending_{port} <= prof_pending_{port} + ((m_axi_{port}_ARVALID && m_axi_{port}_ARREADY) ? ({{8'b0,m_axi_{port}_ARLEN}}+16'd1) : 16'd0) - (m_axi_{port}_RVALID && m_axi_{port}_RREADY);\nend\n"
logic=pending+'\nalways @(*) begin\n prof_increment=0;\n case(prof_select)\n'
for i,expr in enumerate(adds): logic+=f' 5\'d{i}: prof_increment=({expr});\n'
logic+=' endcase\nend\nalways @(posedge ap_clk) begin\n if(!ap_rst_n || (ap_CS_fsm_state1 && ap_start)) begin\n  prof_total<=0; prof_selected<=0;\n end else if(!ap_CS_fsm_state1) begin\n  prof_total<=prof_total+1; prof_selected<=prof_selected+prof_increment;\n end\nend\n'
a=s.rfind('endmodule');s=s[:a]+logic+s[a:];save('conv',s)
s=read('conv_CTRL_s_axi');s=s.replace('    input  wire                          ACLK,', '    input wire [21:0] prof_total, prof_selected,\n    output reg [4:0] prof_select,\n    input  wire                          ACLK,')
s=s.replace('            case (raddr)',"            case (raddr)\n                8'hbc: rdata <= 32'h43545231;\n                8'hb0: rdata <= prof_select;\n                8'hc0: rdata <= prof_total;\n                8'hc4: rdata <= prof_selected;")
a=s.rfind('endmodule');s=s[:a]+"always @(posedge ACLK) begin\n if(ARESET) prof_select<=0;\n else if(ACLK_EN && w_hs && waddr==8'hb0 && WSTRB[0]) prof_select<=WDATA[4:0];\nend\n"+s[a:];save('conv_CTRL_s_axi',s)
names=['total','parameters','bias_init','input_load','weight_load','compute','load_compute','store','quantize','write','compute_load_overlap','read_beats','write_beats','read_backpressure','write_backpressure','load_without_compute','read_response_gap','read_gap_without_compute']
(test/'counters.json').write_text(json.dumps(names,indent=2)+'\n')
print('Patched temporary IP:',ip)
