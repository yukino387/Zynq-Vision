connect -url tcp:127.0.0.1:3121
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
puts "RX: [mrd 0x0010c180 20]"
puts "TX: [mrd 0x0010d188 8]"
disconnect
exit
