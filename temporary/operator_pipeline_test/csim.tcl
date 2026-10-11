set root [file normalize [file join [file dirname [info script]] ../..]]
open_project [file join $root temporary operator_pipeline_test build $::env(HLS_VARIANT)]
open_solution solution
csim_design
exit
