connect -url tcp:127.0.0.1:3121
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
if {[catch {stop} e]} {puts "stop: $e"}
after 100
puts "PC=[rrd pc]"
puts "UDP0=[mrd -value 0x1248540]"
puts "UDP1=[mrd -value 0x1248544]"
puts "UDP2=[mrd -value 0x1248548]"
con
disconnect
exit
