connect -url tcp:127.0.0.1:3121
configparams force-mem-accesses 1
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
catch {stop}
proc rd {addr} {
    set line [mrd $addr 1]
    return [expr 0x[lindex $line end]]
}
proc mdio {phy reg} {
    set mgtcr [expr {0x40020000 | 0x20000000 | ($phy << 23) | ($reg << 18)}]
    mwr 0xE000B034 $mgtcr
    for {set i 0} {$i < 1000} {incr i} {
        if {[expr {[rd 0xE000B008] & 4}]} { break }
    }
    return [expr {[rd 0xE000B034] & 0xFFFF}]
}
puts "NWCFG: [format 0x%08X [rd 0xE000B004]]"
foreach phy {0 1 2 3 4 5 6 7} {
    puts "phy $phy reg1(BMSR)=[format 0x%04X [mdio $phy 1]] reg17=[format 0x%04X [mdio $phy 17]]"
}
con
disconnect
