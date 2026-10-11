set testdir [file dirname [file normalize [info script]]]
set root [file normalize [file join $testdir ../..]]
set log [open [file join $testdir result.log] w]
set failed 0
set bp {}
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
    dow [file join $testdir build/camera_test.elf]
    set bp [bpadd -addr &camera_test_finished -type hw]
    con -block -timeout 25
    foreach variable {camera_stage camera_errors camera_frames camera_hash camera_min camera_max} {
        puts $log "$variable = [print $variable]"
    }
    if {[dict get [print -dict camera_errors] camera_errors] != 0 ||
        [dict get [print -dict camera_frames] camera_frames] != 3} {
        error "Camera frame capture failed"
    }
    source [file join $testdir build/addresses.tcl]
    mrd -bin -file [file join $testdir frame.bin] [dict get $addresses camera_pixels] 86528
    mrd -bin -file [file join $testdir input.bin] [dict get $addresses camera_input] 259584
    puts $log "PASS: three camera frames, DMA guards and CHW range verified"
} message]} {
    catch {stop}
    puts $log "FAIL: $message"
    set failed 1
}
if {$bp ne {}} {catch {bpremove $bp}}
catch {disconnect}
close $log
exit $failed
