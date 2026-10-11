set testdir [file dirname [info script]]
set log [open [file join $testdir result.log] w]
set bp ""
set failed 0
set timed_out 0
if {[catch {
    connect -url tcp:127.0.0.1:3121
    targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
    catch {stop}
    source [file join $testdir .. .. cnn_app _ide psinit ps7_init.tcl]
    puts $log "Initializing PS with existing ps7_init.tcl"
    flush $log
    rst -system
    after 500
    ps7_init
    puts $log "Loading existing bitstream"
    flush $log
    targets -set -filter {name =~ "xc7z020"}
    fpga -file [file join $testdir .. .. cnn_app _ide bitstream cnn_accelerator.bit]
    targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
    catch {stop}
    ps7_post_config
    configparams force-mem-accesses 1
    puts $log "CTRL before download: [mrd 0x43c00000]"
    flush $log
    dow [file join $testdir build basic_op_test.elf]
    set bp [bpadd -addr &test_finished -type hw]
    if {[catch {con -block -timeout 40} run_error]} {
        catch {stop}
        puts $log "RUN ERROR: $run_error"
        set timed_out 1
    }
    foreach expr {test_stage test_errors test_checked conv_inst.Ctrl_BaseAddress conv_inst.IsReady} {
        puts $log "$expr = [print $expr]"
    }
    puts $log "CTRL after run: [mrd 0x43c00000]"
    if {$timed_out} {error "Hardware run did not finish within 40 seconds"}
    set stage [dict get [print -dict test_stage] test_stage]
    set errors [dict get [print -dict test_errors] test_errors]
    set checked [dict get [print -dict test_checked] test_checked]
    if {$stage != 4 || $errors != 0 || $checked != 1384448} {
        error "Output verification failed"
    }
    puts $log "PASS: two calls, 1384448 outputs checked, zero mismatches"
} message]} {
    puts $log "TEST ERROR: $message"
    set failed 1
}
if {$bp ne ""} {catch {bpremove $bp}}
catch {disconnect}
close $log
exit $failed
