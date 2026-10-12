set root [file normalize [file join [file dirname [info script]] ../..]]
set ::env(HLS_SHARED_CORE) 1
set ::env(HLS_INPUT256) 1
open_project [file join $root temporary realtime_256_test build conv]
open_solution solution
cosim_design -rtl verilog -trace_level none -random_stall
exit
