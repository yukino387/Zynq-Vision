if {[catch {
set root {C:/00_workplace/fpga/cnn_accelerator}
set out [file join $root temporary/camera_quality_test/build]
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
set bp [bpadd -addr &quality_finished -type hw]
con -block -timeout 45
bpremove $bp
source [file join $out symbols.tcl]
set errors [mrd -value $quality_error]
set f [open [file join $out probe_result.log] w]
puts $f "ERROR [mrd -value $quality_error]"
puts $f "MISMATCH [mrd -value $differing_pixels 64]"

close $f
mrd -bin -file [file join $out elapsed_us.bin] $elapsed_us 64
mrd -bin -file [file join $out differing_pixels.bin] $differing_pixels 64
mrd -bin -file [file join $out bars.rgb565] $bar_images 173088
if {$errors != 0} {error "Camera probe failed: $errors"}
disconnect

} message]} {puts $message; puts $::errorInfo; exit 1}
exit 0
