connect -url tcp:127.0.0.1:3121
configparams force-mem-accesses 1
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
catch {stop}
foreach off {0x00 0x04 0x08 0x10 0x14 0x18 0x1C 0x20 0x24 0x30 0x34} {
    catch {puts "E000B0$off = [mrd [expr 0xE000B000 + $off] 1]"} msg
    if {[string match "Memory read error*" $msg] || [string match "Blocked*" $msg]} { puts "E000B0$off blocked" }
}
con
disconnect
