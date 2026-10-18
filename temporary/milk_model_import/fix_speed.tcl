connect -url tcp:127.0.0.1:3121
configparams force-mem-accesses 1
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
catch {stop}
set nwcfg [mrd 0xE000B004 1]
puts "before: $nwcfg"
mwr 0xE000B004 0x011F20C3
puts "after: [mrd 0xE000B004 1]"
con
disconnect
