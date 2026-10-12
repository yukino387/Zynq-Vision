set root [file normalize [file join [file dirname [info script]] ../..]]
connect -url tcp:127.0.0.1:3121
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
catch {stop}
rst -system
after 500
source [file join $root vitis_live camera_platform_live hw sdt ps7_init.tcl]
ps7_init
targets -set -filter {name =~ "xc7z020"}
fpga -file [file join $root hardware camera build system_wrapper.bit]
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
ps7_post_config
configparams force-mem-accesses 1
dow [file join $root temporary realtime_256_test build camera_probe.elf]
set done [bpadd -addr &probe_done -type hw]
con -block -timeout 15
bpremove $done
set nm C:/AMDDesignTools/2026.1/Vitis/gnu/aarch32/nt/gcc-arm-none-eabi/bin/arm-none-eabi-nm.exe
set address {}
foreach line [split [exec $nm [file join $root temporary realtime_256_test build camera_probe.elf]] "\n"] {
    if {[regexp {^([0-9a-fA-F]+)\s+\w\s+probe_result$} [string trim $line] unused value]} {set address 0x$value}
}
if {$address eq {}} {error "Probe result symbol missing"}
puts [mrd $address 40]
disconnect
exit
