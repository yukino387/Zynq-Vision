if {[catch {
set root {C:/00_workplace/fpga/cnn_accelerator}
set out [file join $root temporary/camera_fps_test/build]
connect -url tcp:127.0.0.1:3121
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
catch {stop}
rst -system
after 500
source [file join $root vitis_live/camera_platform_live/export/camera_platform_live/hw/sdt/ps7_init.tcl]
ps7_init
targets -set -filter {name =~ "xc7z020"}
fpga -file [file join $root hardware/camera/build/system_wrapper.bit]
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
ps7_post_config
configparams force-mem-accesses 1
dow [file join $out probe.elf]
set bp [bpadd -addr &probe_finished -type hw]
con -block -timeout 45
bpremove $bp
source [file join $out symbols.tcl]
set errors [mrd -value $probe_error]
if {$errors != 0} {error "Camera probe failed: $errors"}
set f [open [file join $out probe_result.log] w]
puts $f "ERROR [mrd -value $probe_error]"
puts $f "CAPTURE_US [mrd -value $capture_us 24]"
puts $f "SENSOR [mrd -value $sensor_values 12]"
close $f
mrd -bin -file [file join $out capture_us.bin] $capture_us 24
mrd -bin -file [file join $out sensor_values.bin] $sensor_values 12
mrd -bin -file [file join $out probe_pixels.rgb565] $probe_pixels 86528
disconnect

} message]} {puts $message; puts $::errorInfo; exit 1}
exit 0
