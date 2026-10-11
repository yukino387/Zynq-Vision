set root [file normalize [file join [file dirname [info script]] ../..]]
set variant baseline
if {[info exists ::env(HLS_VARIANT)]} {set variant $::env(HLS_VARIANT)}
open_project [file join $root temporary operator_pipeline_test build $variant]
open_solution solution
cosim_design -rtl verilog -trace_level none
exit
