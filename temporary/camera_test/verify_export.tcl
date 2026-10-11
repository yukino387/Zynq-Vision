set root [file normalize [file join [file dirname [info script]] ../..]]
set build [file join $root hardware/camera/build]
open_project [file join $build camera_cnn.xpr]
open_checkpoint [file join $build routed.dcp]
report_bus_skew -file [file join $build bus_skew.rpt]
write_hw_platform -fixed -include_bit -force -file [file join $build camera_cnn.xsa]
exit
