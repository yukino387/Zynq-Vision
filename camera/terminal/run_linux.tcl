# Headless RAM commissioning; does not write SD or QSPI.
set root [file normalize [file join [file dirname [info script]] ../..]]
set hardware [file join $root hardware/camera/build/terminal]
set boot [file join $root camera/terminal/build/delivery/boot]
set initrd [file join $boot initramfs.cpio.gz]
proc stage {message} {puts $message; flush stdout}
proc stop_private_watchdog {} {
    mwr -force 0xf8f00634 0x12345678
    mwr -force 0xf8f00634 0x87654321
    mwr -force 0xf8f00628 0
    set control [lindex [mrd -value -force 0xf8f00628] 0]
    if {$control != 0} {error "Private watchdog still active: $control"}
    stage PRIVATE-WATCHDOG-DISABLED
}
foreach path [list $initrd [file join $hardware qualified.dcp] [file join $hardware system_wrapper.bit] [file join $boot zImage] [file join $boot system.dtb] [file join $boot u-boot.elf]] {
    if {![file isfile $path]} {error "Missing terminal artifact: $path"}
}
connect -url tcp:127.0.0.1:3121
jtag targets -set -filter {level == 0}
jtag frequency 10000000
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
catch {stop}
configparams force-mem-accesses 1
stop_private_watchdog
rst -system -stop
after 500
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #1"}
catch {stop}
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
catch {stop}
configparams force-mem-accesses 1
stop_private_watchdog
source [file join $root camera/terminal/build/vitis/vision_terminal_platform/export/vision_terminal_platform/hw/sdt/ps7_init.tcl]
# Generated delays use the CPU global timer, which is stopped during JTAG init.
proc mask_delay {addr delay} {after $delay}
proc mask_poll {addr mask} {
    set deadline [expr {[clock milliseconds] + 10000}]
    while {1} {
        set value [lindex [mrd -value -force $addr] 0]
        if {($value & $mask) != 0} {return}
        if {[clock milliseconds] > $deadline} {error "PS init timeout at $addr: $value"}
        after 10
    }
}
ps7_init
stage PS-INITIALIZED
targets -set -filter {name =~ "xc7z020"}
fpga -file [file join $hardware system_wrapper.bit]
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
ps7_post_config
configparams force-mem-accesses 1
stop_private_watchdog
rst -processor -clear-registers
after 250
dow [file join $boot u-boot.elf]
set first [lindex [mrd -value -force 0x04000000] 0]
if {$first != 0xea0000b8} {error "Unexpected U-Boot entry word: $first"}
stage UBOOT-LOADED
dow -data [file join $boot zImage] 0x02000000
stage KERNEL-LOADED
dow -data [file join $boot system.dtb] 0x08000000
stage DEVICE-TREE-LOADED
dow -data $initrd 0x10000000
stage INITRAMFS-LOADED
stop_private_watchdog
rwr cpsr 0xd3
rwr pc 0x04000000
stage "RAM-READY initrd_bytes=[file size $initrd]"
stage [format {UART: setenv bootargs console=ttyPS0,115200 rdinit=/sbin/init cma=64M; bootz 0x02000000 0x10000000:%x 0x08000000} [file size $initrd]]
con
disconnect
exit
