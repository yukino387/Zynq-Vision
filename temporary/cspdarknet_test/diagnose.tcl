connect -url tcp:127.0.0.1:3121
configparams force-mem-accesses 1
puts [targets]
targets -set -filter {name == "APU"}
foreach address {0x43c00000 0x43c00078 0x43c00080 0x43c00088 0x43c00098} {
    if {[catch {mrd $address} value]} {puts "$address ERROR: $value"} else {puts $value}
}
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
catch {stop} message
puts $message
catch {rrd pc} message
puts $message
disconnect
exit
