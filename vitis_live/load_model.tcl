set workspace [file dirname [file normalize [info script]]]
set root [file dirname $workspace]
set elf [file join $workspace camera_live/build/camera_live.elf]
connect -url tcp:127.0.0.1:3121
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
catch {stop}
rst -system
after 500
source [file join $workspace camera_platform_live/export/camera_platform_live/hw/sdt/ps7_init.tcl]
ps7_init
targets -set -filter {name =~ "xc7z020"}
fpga -file [file join $root hardware/camera/build/system_wrapper.bit]
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
ps7_post_config
configparams force-mem-accesses 1
dow $elf
con
