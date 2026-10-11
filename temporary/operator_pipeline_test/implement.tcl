set root [file normalize [file join [file dirname [info script]] ../..]]
set variant $::env(HLS_VARIANT)
set build [file join $root temporary operator_pipeline_test build]
open_project [file join $build $variant]
open_solution solution
export_design -rtl verilog -format ip_catalog -flow impl -output [file join $build ${variant}.zip]
exit
