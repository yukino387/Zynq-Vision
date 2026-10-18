connect -url tcp:127.0.0.1:3121
configparams force-mem-accesses 1
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
catch {stop}
puts "before: [mrd 0xE000B004 1]"
mwr 0xE000B004 0x011F24C2
puts "after: [mrd 0xE000B004 1]"
con
disconnect
