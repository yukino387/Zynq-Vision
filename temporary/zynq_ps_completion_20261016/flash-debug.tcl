connect -url tcp:127.0.0.1:3121
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
puts [mrd 0x03000000 18]
puts [mrd 0x08000000 16]
disconnect
exit
