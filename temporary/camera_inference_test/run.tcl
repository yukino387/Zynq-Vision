set testdir [file dirname [file normalize [info script]]]
set root [file normalize [file join $testdir ../..]]
set log [open [file join $testdir result.log] w]
set breakpoints {}
set failed 0
if {[catch {
    connect -url tcp:127.0.0.1:3121
    targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
    catch {stop}
    rst -system
    after 500
    source [file join $root hardware/camera/build/camera_cnn.gen/sources_1/bd/system/ip/system_processing_system7_0_0/ps7_init.tcl]
    ps7_init
    targets -set -filter {name =~ "xc7z020"}
    fpga -file [file join $root hardware/camera/build/system_wrapper.bit]
    targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
    ps7_post_config
    configparams force-mem-accesses 1
    dow [file join $testdir build/camera_inference_test.elf]
    set ready [bpadd -addr &test_load_ready -type hw]
    lappend breakpoints $ready
    con -block -timeout 20
    bpremove $ready
    set breakpoints {}
    source [file join $testdir build/camera_inference_test-addresses.tcl]
    foreach {name file} {raw_files all_weights.bin pc_directory directory.bin} {
        puts "Loading $file into DDR"
        dow -data [file join $root temporary/full_weight_test/pc_files $file] [dict get $addresses $name]
    }
    puts "Running camera inference and UDP test"
    lappend breakpoints [bpadd -addr &test_finished -type hw]
    con -block -timeout 100
    foreach variable {test_stage test_errors test_loaded test_frames forward_us capture_us conversion_us transfer_us cycle_us} {
        puts $log "$variable = [print $variable]"
    }
    if {[dict get [print -dict test_errors] test_errors] != 0 ||
        [dict get [print -dict test_frames] test_frames] != 3} {error "Camera inference test failed"}
    mrd -bin -file [file join $testdir jtag_out0.bin] [dict get $addresses out0_storage] 6338
    mrd -bin -file [file join $testdir jtag_out1.bin] [dict get $addresses out1_storage] 25350
    mrd -bin -file [file join $testdir jtag_preview.bin] [dict get $addresses pixels] 86528
    puts $log "PASS: camera -> real YOLO FPGA forward -> UDP, three frames sent"
} message]} {
    catch {stop}
    puts $log "FAIL: $message"
    set failed 1
}
foreach bp $breakpoints {catch {bpremove $bp}}
catch {disconnect}
close $log
exit $failed
