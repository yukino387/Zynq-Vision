connect -url tcp:127.0.0.1:3121
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
puts "state: [state]"
catch {stop} msg
puts "stop: $msg"
puts "state-after-stop: [state]"
puts "pc: [rrd pc]"
puts "lr: [rrd lr]"
puts "sp: [rrd sp]"
puts "cpsr: [rrd cpsr]"
