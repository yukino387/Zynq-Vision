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
    ps7_post_config
    configparams force-mem-accesses 1
    dow [file join $testdir build full_weight_test.elf]
    set ready [bpadd -addr &test_load_ready -type hw]
    lappend breakpoints $ready
    con -block -timeout 20
    bpremove $ready
    set breakpoints {}
    source [file join $testdir build addresses.tcl]
    foreach {name file} {raw_files all_weights.bin pc_directory directory.bin} {
        puts $log "Staging PC file $file"
        flush $log
        dow -data [file join $testdir pc_files $file] [dict get $addresses $name]
    }
    lappend breakpoints [bpadd -addr &test_finished -type hw]
    con -block -timeout 55
    foreach expr {test_stage test_errors test_loaded test_verified test_checked} {
        puts $log "$expr = [print $expr]"
    }
    for {set i 0} {$i < 42} {incr i} {
        puts $log "file_results\[$i\] = [print file_results\[$i\]]"
    }
    set stage [dict get [print -dict test_stage] test_stage]
    set errors [dict get [print -dict test_errors] test_errors]
    set loaded [dict get [print -dict test_loaded] test_loaded]
    set verified [dict get [print -dict test_verified] test_verified]
    set checked [dict get [print -dict test_checked] test_checked]
    if {$stage != 3 || $errors != 0 || $loaded != 42 || $verified != 42 || $checked != [file size [file join $testdir pc_files all_weights.bin]] / 4} {
        error "Full-network weight verification failed"
    }
    puts $log "PASS: 21 layers, 42 files; all counts, min/max and quantized parameter hashes match PC reference. No forward executed."
} message]} {
    puts $log "TEST ERROR: $message"
    set failed 1
}
foreach bp $breakpoints {catch {bpremove $bp}}
catch {disconnect}
close $log
exit $failed
