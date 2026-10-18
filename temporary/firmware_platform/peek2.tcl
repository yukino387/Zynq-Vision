connect -url tcp:127.0.0.1:3121
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
if {[catch {stop} e]} {puts "stop: $e"}
after 100
puts "PC=[rrd pc]"
puts "NWCTRL=[mrd -value 0xe000b000]"
puts "NWSTATUS=[mrd -value 0xe000b008]"
puts "DMACTRL=[mrd -value 0xe000b010]"
puts "PHYMNT=[mrd -value 0xe000b034]"
puts "RXQBASE=[mrd -value 0xe000b018]"
puts "TXQBASE=[mrd -value 0xe000b01c]"
con
disconnect
exit
