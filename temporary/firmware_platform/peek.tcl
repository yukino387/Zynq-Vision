connect -url tcp:127.0.0.1:3121
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
if {[catch {stop} e]} {puts "stop: $e"}
after 200
puts "PC=[rrd pc]"
puts "CPSR=[rrd cpsr]"
puts "LR=[rrd lr]"
puts "SP=[rrd sp]"
con
disconnect
exit
