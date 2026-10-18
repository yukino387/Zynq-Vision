connect -url tcp:127.0.0.1:3121
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
catch {stop}
set spv [lindex [rrd sp] 1]
set pcv [lindex [rrd pc] 1]
set lrv [lindex [rrd lr] 1]
puts "pc=$pcv sp=$spv lr=$lrv"
puts [mrd [expr 0x$spv] 64]
con
disconnect
