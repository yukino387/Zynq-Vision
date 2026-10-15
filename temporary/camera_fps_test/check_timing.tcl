set root {C:/00_workplace/fpga/cnn_accelerator}
set out [file join $root temporary/camera_fps_test/build]
set_param general.maxThreads 16
open_checkpoint [file join $root hardware/camera/build/qualified.dcp]
create_clock -name cam_pclk -period 17.857 [get_ports cam_pclk]
report_timing_summary -file [file join $out timing_56mhz.rpt]
report_timing -from [get_ports {cam_data[*] cam_href cam_vsync}] -delay_type max -max_paths 5 -file [file join $out camera_inputs.rpt]
report_bus_skew -file [file join $out bus_skew.rpt]
set f [open [file join $out clock_paths.csv] w]
puts $f {clock,setup_slack,hold_slack}
foreach name {cam_pclk clk_fpga_0} {
 set setup [get_timing_paths -delay_type max -group $name -max_paths 1]
 set hold [get_timing_paths -delay_type min -group $name -max_paths 1]
 puts $f "$name,[get_property SLACK $setup],[get_property SLACK $hold]"
}
close $f
write_checkpoint -force [file join $out qualified_56mhz.dcp]
close_design
exit
