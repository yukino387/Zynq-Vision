set test [file dirname [file normalize [info script]]]
set base [file join $test build]
set source [file join $base shared44_weight_lanes_area_system_166 build]
set stage [file join $base shared44_weight_lanes_reclock_area_system_142 build]
file mkdir $stage
set init [file join $base shared44_weight_lanes_area_system_142 build camera_cnn.gen sources_1 bd system ip system_processing_system7_0_0 ps7_init.tcl]
set stream [open $init r]
set init_text [read $stream]
close $stream
if {[regexp -all {mask_write 0XF8000170 0x03F03F30 0x00100700} $init_text] != 3} {
    error "PS initialization does not select 1 GHz / 7"
}
puts "ACTUAL_FCLK_MHZ=142.857132"
open_checkpoint [file join $source postroute.dcp]
set pin [get_pins -hier -filter {NAME =~ */PS7_i/FCLKCLK[0]}]
if {[llength $pin] != 1} {error "FCLK source pin missing"}
create_clock -name clk_fpga_0 -period 7.0 -waveform {0 3.5} $pin
if {abs([get_property PERIOD [get_clocks clk_fpga_0]] - 7.0) > 0.000001} {
    error "FCLK timing period mismatch"
}
report_utilization -file [file join $stage postroute_utilization.rpt]
report_timing_summary -file [file join $stage postroute_timing.rpt]
report_bus_skew -file [file join $stage postroute_bus_skew.rpt]
write_checkpoint -force [file join $stage postroute.dcp]
puts [exec C:/Users/YUKINO/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -I [file join $test verify_system.py] shared44_weight_lanes_reclock 142]
foreach name {mixed boundary p4} {
    set stream [open [file join $base shared44_weight_lanes_${name}_stall_cosim_console.log] r]
    set log [read $stream]
    close $stream
    if {[string first {C/RTL co-simulation finished: PASS} $log] < 0} {error "$name RTL not verified"}
}
file copy -force $init [file join $stage ps7_init.tcl]
write_bitstream -force [file join $stage system_wrapper.bit]
exit
