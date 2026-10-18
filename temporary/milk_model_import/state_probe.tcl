connect -url tcp:127.0.0.1:3121
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
catch {stop}
puts "running@138e48: [mrd 0x00138e48 1]"
puts "peer/preview@1248540: [mrd 0x01248540 8]"
puts "lwip globals? 0x1248500: [mrd 0x01248500 16]"
con
disconnect
