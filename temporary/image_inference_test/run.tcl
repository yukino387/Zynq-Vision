set testdir [file dirname [info script]]
set log [open [file join $testdir result.log] w]
set breakpoints {}
set failed 0
if {[catch {
    connect -url tcp:127.0.0.1:3121
    targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
    catch {stop}
    source [file join $testdir .. .. cnn_app _ide psinit ps7_init.tcl]
    rst -system
    after 500
    ps7_init
    targets -set -filter {name =~ "xc7z020"}
    fpga -file [file join $testdir .. .. cnn_app _ide bitstream cnn_accelerator.bit]
    targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
    catch {stop}
    ps7_post_config
    configparams force-mem-accesses 1
    dow [file join $testdir build image_inference_test.elf]
    set ready [bpadd -addr &test_load_ready -type hw]
    lappend breakpoints $ready
    con -block -timeout 20
    bpremove $ready
    set breakpoints {}
    source [file join $testdir build addresses.tcl]
    foreach {name file} {raw_files all_weights.bin pc_directory directory.bin input_data input.bin} {
        puts $log "Staging PC file $file"
        flush $log
        dow -data [file join $testdir pc_files $file] [dict get $addresses $name]
    }
    lappend breakpoints [bpadd -addr &test_finished -type hw]
    con -block -timeout 55
    foreach expr {test_stage test_errors test_loaded test_verified test_checked input_min input_max out0_min out0_max out1_min out1_max forward_us timer_counts_per_second out0_changed out1_changed} {
        puts $log "$expr = [print $expr]"
    }
    set stage [dict get [print -dict test_stage] test_stage]
    set errors [dict get [print -dict test_errors] test_errors]
    set loaded [dict get [print -dict test_loaded] test_loaded]
    set verified [dict get [print -dict test_verified] test_verified]
    if {$stage != 4 || $errors != 0 || $loaded != 42 || $verified != 42} {
        error "Image inference verification failed"
    }
    # mrd exports 32-bit words; report.py removes the final padding halfword.
    mrd -bin -file [file join $testdir out0.bin] [expr {[dict get $addresses out0_storage] + 64}] 6338
    mrd -bin -file [file join $testdir out1.bin] [expr {[dict get $addresses out1_storage] + 64}] 25350
    puts $log "PASS: real weights + real RGB image forward completed; output guards intact. Raw int16 outputs exported."
} message]} {
    catch {stop}
    puts $log "TEST ERROR: $message"
    puts $log "State: [catch {print test_stage} state]; $state"
    set failed 1
}
foreach bp $breakpoints {catch {bpremove $bp}}
catch {disconnect}
close $log
exit $failed
