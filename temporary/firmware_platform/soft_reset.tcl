connect -url tcp:127.0.0.1:3121
targets -set -filter {name == "APU"}
rst -system
after 1500
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
con
after 500
disconnect
exit
