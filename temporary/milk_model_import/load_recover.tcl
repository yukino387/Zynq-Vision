set workspace C:/00_workplace/fpga/cnn_accelerator/vitis_live
set root C:/00_workplace/fpga/cnn_accelerator
connect -url tcp:127.0.0.1:3121
puts "targets: [targets]"
if {[llength [targets -filter {name =~ "APU"}]] == 0} {
    puts "recovering DAP"
    targets -set 1
    catch {rst -system} msg
    puts "dap reset: $msg"
    after 1500
}
puts "after recover: [targets]"
targets -set -filter {name =~ "APU"}
catch {rst -system} msg
puts "system reset: $msg"
after 1000
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
catch {stop} msg
puts "core state: [state]"
source [file join $workspace camera_platform_live/export/camera_platform_live/hw/sdt/ps7_init.tcl]
ps7_init
puts "ps7_init done"
targets -set -filter {name =~ "xc7z020"}
fpga -file [file join $root hardware/camera/build/system_wrapper.bit]
puts "bitstream done"
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
ps7_post_config
puts "post config done"
configparams force-mem-accesses 1
dow [file join $workspace camera_live/build/camera_live.elf]
puts "elf done"
con
puts "running: [state]"
disconnect
