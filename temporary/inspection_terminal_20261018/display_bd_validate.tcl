set_param general.maxThreads 16
set task [file dirname [file normalize [info script]]]
file delete -force [file join $task display-bd.PASS]
set root [file normalize [file join $task ../..]]
create_project display_bd [file join $task display_bd] -part xc7z020clg400-2 -force
set_property ip_repo_paths [file join $root hardware/hls/build/conv/hls/impl/ip] [current_project]
update_ip_catalog
set_property XPM_LIBRARIES {XPM_FIFO} [current_project]
source [file join $root hardware/camera/base_system.tcl]
set ps [get_bd_cells processing_system7_0]
set_property CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100.000000} $ps
source [file join $root hardware/display/integrate.tcl]
validate_bd_design
save_bd_design
set marker [open [file join $task display-bd.PASS] w]
puts $marker "display block design validated"
close $marker
exit
