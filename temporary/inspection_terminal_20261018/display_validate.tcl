set_param general.maxThreads 16
set task [file dirname [file normalize [info script]]]
file delete -force [file join $task display.PASS]
file delete -force [file join $task display_sim/display_sim.sim/sim_1/behav/xsim/logic.PASS]
set root [file normalize [file join $task ../..]]
create_project display_sim [file join $task display_sim] -part xc7z020clg400-2 -force
set_property XPM_LIBRARIES {XPM_FIFO} [current_project]
add_files [glob [file join $root hardware/display/*.v]]
add_files -fileset sim_1 [file join $task display_tb.sv]
set_property top display_tb [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
launch_simulation -simset sim_1 -mode behavioral
close_sim
set proof [file join $task display_sim/display_sim.sim/sim_1/behav/xsim/logic.PASS]
if {![file exists $proof]} {error "Display logic simulation did not produce PASS marker"}
set_property top hdmi_scanout [current_fileset]
synth_design -top hdmi_scanout -part xc7z020clg400-2 -mode out_of_context
report_utilization -file [file join $task display_utilization.rpt]
write_checkpoint -force [file join $task display_synthesized.dcp]
set marker [open [file join $task display.PASS] w]
puts $marker "simulation and out-of-context synthesis passed"
close $marker
exit
