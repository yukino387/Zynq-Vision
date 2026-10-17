set root [file normalize [lindex $argv 0]]
set helper [file normalize [lindex $argv 1]]
set image [file normalize [lindex $argv 2]]
set backup [file normalize [lindex $argv 3]]
set bytes [lindex $argv 4]
set erase_size [expr {(($bytes+65535)/65536)*65536}]
set expected_sha [lindex $argv 5]
connect -url tcp:127.0.0.1:3121
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
catch {stop}
rst -system -stop
after 500
targets -set -filter {name == "APU"}
source [file join $root vitis_live/camera_platform_live/export/camera_platform_live/hw/sdt/ps7_init.tcl]
ps7_init
ps7_post_config
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
if {[catch {stop} stop_error] && [string first {Already stopped} $stop_error] < 0} {error $stop_error}
configparams force-mem-accesses 1
proc execute {operation bytes} {
    global helper
    dow $helper
    mwr 0x03000000 $operation
    mwr 0x03000004 $bytes
    con
    set deadline [expr {[clock milliseconds]+240000}]
    while {1} {
        after 1000
        set state [mrd -value 0x03000008]
        if {$state == 0x444f4e45} {break}
        if {[clock milliseconds]>$deadline} {stop;error "QSPI helper timed out"}
    }
    stop
    set error_code [mrd -value 0x03000010]
    set jedec [mrd -value 0x03000014]
    puts "QSPI phase=$operation JEDEC=$jedec error=$error_code"
    if {$error_code != 0 || $jedec != 0xef4019} {error "QSPI helper rejected operation"}
}
execute 1 $erase_size
mrd -bin -file $backup 0x08000000 [expr {$erase_size/4}]
if {[file size $backup] != $erase_size} {error "Flash backup length mismatch"}
puts "QSPI_BACKUP_SAVED=$backup"
dow -data $image 0x08000000
execute 2 $bytes
set verified [mrd -value 0x0300000c]
if {$verified != $bytes} {error "Flash readback verification was incomplete"}
set actual_sha ""
foreach value [mrd -size b -value 0x03000018 32] {append actual_sha [format %02x $value]}
if {![string equal -nocase $actual_sha $expected_sha]} {error "JTAG image SHA256 mismatch"}
puts "QSPI_PROGRAM_VERIFIED bytes=$bytes sha256=$actual_sha"
disconnect
exit
