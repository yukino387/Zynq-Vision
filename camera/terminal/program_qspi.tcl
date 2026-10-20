set root [file normalize [lindex $argv 0]]
set helper [file normalize [lindex $argv 1]]
set image [file normalize [lindex $argv 2]]
set backup [file normalize [lindex $argv 3]]
set bytes [lindex $argv 4]
set expected_sha [lindex $argv 5]
set erase_size [expr {(($bytes+65535)/65536)*65536}]
if {$bytes <= 0 || $erase_size > 0x007fe000 || [file size $image] != $bytes} {error "Invalid terminal QSPI image extent"}
if {[file exists $backup]} {error "Refusing to overwrite an existing Flash backup"}
proc stop_private_watchdog {} {
    mwr -force 0xf8f00634 0x12345678
    mwr -force 0xf8f00634 0x87654321
    mwr -force 0xf8f00628 0
    if {[lindex [mrd -value -force 0xf8f00628] 0] != 0} {error "Private watchdog still active"}
}
connect -url tcp:127.0.0.1:3121
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
catch {stop}
configparams force-mem-accesses 1
rst -system -stop
after 500
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #1"}
catch {stop}
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
catch {stop}
configparams force-mem-accesses 1
stop_private_watchdog
source [file join $root camera/terminal/build/vitis/vision_terminal_platform/export/vision_terminal_platform/hw/sdt/ps7_init.tcl]
proc mask_delay {addr delay} {after $delay}
proc mask_poll {addr mask} {
    set deadline [expr {[clock milliseconds]+10000}]
    while {1} {
        if {([lindex [mrd -value -force $addr] 0] & $mask) != 0} {return}
        if {[clock milliseconds]>$deadline} {error "PS initialization timeout at $addr"}
        after 10
    }
}
ps7_init
ps7_post_config
stop_private_watchdog
proc execute {operation bytes} {
    global helper
    dow $helper
    mwr 0x03000000 $operation
    mwr 0x03000004 $bytes
    mwr 0x03000038 0
    mwr 0x0300003c 0
    con
    set deadline [expr {[clock milliseconds]+240000}]
    while {1} {
        after 1000
        if {[mrd -value 0x03000008] == 0x444f4e45} {break}
        if {[clock milliseconds]>$deadline} {stop;error "QSPI helper timed out"}
    }
    stop
    set error_code [mrd -value 0x03000010]
    set jedec [mrd -value 0x03000014]
    puts [format "QSPI phase=%d JEDEC=%06x capacity_bytes=33554432 error=%d" $operation $jedec $error_code]
    flush stdout
    if {$error_code != 0 || $jedec != 0xef4019} {error "QSPI helper rejected operation"}
}
execute 1 $erase_size
mrd -bin -file $backup 0x08000000 [expr {$erase_size/4}]
if {[file size $backup] != $erase_size} {error "Flash backup length mismatch"}
puts "QSPI_BACKUP_SAVED=$backup"
flush stdout
dow -data $image 0x08000000
execute 2 $bytes
if {[mrd -value 0x0300000c] != $bytes} {error "Flash readback verification incomplete"}
set actual_sha ""
foreach value [mrd -size b -value 0x03000018 32] {append actual_sha [format %02x $value]}
if {![string equal -nocase $actual_sha $expected_sha]} {error "JTAG image SHA256 mismatch"}
puts "QSPI_PROGRAM_VERIFIED bytes=$bytes sha256=$actual_sha"
flush stdout
disconnect
exit
