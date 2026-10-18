connect -url tcp:127.0.0.1:3121
configparams force-mem-accesses 1
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
catch {stop}
foreach addr {0x43C00000 0x43C00004 0x43C00008 0x43C0000C 0x43C00010 0x43C000F0 0x43C000FC} {
    catch {puts "$addr = [mrd $addr 1]"} msg
    if {[string match "Memory read error*" $msg]} { puts "$addr READ ERROR" }
}
puts "PCAP status 0xF8007080 = [mrd 0xF8007080 1]"
con
disconnect
