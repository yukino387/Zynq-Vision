set root [file normalize [file join [file dirname [info script]] ../..]]
set test [file join $root temporary operator_pipeline_test]
set mhz $::env(HLS_SYSTEM_MHZ)
if {$mhz ni {142 166}} {error "Unsupported qualification frequency"}
set stage [file join $test build shared44_weight_lanes_area_system_$mhz build]
puts [exec C:/Users/YUKINO/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe -I [file join $test verify_system.py] shared44_weight_lanes $mhz]
foreach name {mixed boundary p4} {
    set stream [open [file join $test build shared44_weight_lanes_${name}_stall_cosim_console.log] r]
    set log [read $stream]
    close $stream
    if {[string first {C/RTL co-simulation finished: PASS} $log] < 0} {
        error "$name RTL verification has not passed"
    }
}
open_checkpoint [file join $stage postroute.dcp]
write_bitstream -force [file join $stage system_wrapper.bit]
close_project
open_project [file join $stage camera_cnn.xpr]
open_bd_design [file join $stage camera_cnn.srcs sources_1 bd system system.bd]
write_hw_platform -fixed -force -file [file join $stage camera_cnn.xsa]
exit
