set root [file normalize [file join [file dirname [info script]] ../..]]
set build [file join $root hardware/camera/build]
open_checkpoint [file join $build synthesized.dcp]
report_property [get_package_pins W14]
set_property CLOCK_DEDICATED_ROUTE FALSE [get_nets cam_pclk_IBUF]
opt_design
write_checkpoint -force [file join $build optimized.dcp]
place_design
phys_opt_design
route_design
report_utilization -file [file join $build utilization.rpt]
report_timing_summary -file [file join $build timing.rpt]
report_bus_skew -file [file join $build bus_skew.rpt]
write_checkpoint -force [file join $build routed.dcp]
write_bitstream -force [file join $build system_wrapper.bit]
exit
