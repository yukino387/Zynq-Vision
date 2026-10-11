set root [file normalize [file join [file dirname [info script]] ../..]]
set build [file join $root hardware/camera/build]
open_project [file join $build camera_cnn.xpr]
write_hw_platform -fixed -force -file [file join $build camera_cnn.xsa]
set_property synth_checkpoint_mode None [get_files system.bd]
generate_target all [get_files system.bd]
update_compile_order -fileset sources_1
synth_design -top system_wrapper -part xc7z020clg400-2
write_checkpoint -force [file join $build synthesized.dcp]
opt_design
place_design
phys_opt_design
route_design
report_utilization -file [file join $build utilization.rpt]
report_timing_summary -file [file join $build timing.rpt]
write_checkpoint -force [file join $build routed.dcp]
write_bitstream -force [file join $build system_wrapper.bit]
write_hw_platform -fixed -include_bit -force -file [file join $build camera_cnn.xsa]
exit
