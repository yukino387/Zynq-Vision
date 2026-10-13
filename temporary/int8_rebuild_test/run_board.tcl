set root {C:/00_workplace/fpga/cnn_accelerator}
set testdir [file join $root temporary int8_rebuild_test build]
set log [open [file join $testdir board result.log] w]
set breakpoints {}
set failed 0
if {[catch {
    connect -url tcp:127.0.0.1:3121
    targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
    catch {stop}
    source [file join $root vitis_live camera_platform_live export camera_platform_live hw sdt ps7_init.tcl]
    rst -system
    after 500
    ps7_init
    mwr 0xF8000008 0xDF0D
    mask_write 0xF8000170 0x03F03F30 0x00100800
    mwr 0xF8000004 0x767B
    puts $log "FCLK0_CTRL = [mrd -value 0xF8000170]"
    targets -set -filter {name =~ "xc7z020"}
    fpga -file [file join $testdir qualified125 system_wrapper.bit]
    targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
    catch {stop}
    ps7_post_config
    configparams force-mem-accesses 1
    dow [file join $testdir board test.elf]
    set ready [bpadd -addr &test_load_ready -type hw]
    lappend breakpoints $ready
    con -block -timeout 20
    bpremove $ready
    set breakpoints {}
    source [file join $testdir board addresses.tcl]
    foreach name {features weights metadata} {
        puts "Staging $name"
        dow -data [file join $testdir $name.bin] [dict get $addresses $name]
    }
    dow -data [file join $testdir gray_pixels.bin] [dict get $addresses gray_pixels]
    lappend breakpoints [bpadd -addr &test_finished -type hw]
    con -block -timeout 20
    foreach expr {test_stage test_errors forward_us preprocessing_us stage_hashes} {
        puts $log "$expr = [print $expr]"
    }
    puts $log "FORWARD_US = [mrd -value [dict get $addresses forward_us] 3]"
    source [file join $testdir layout.tcl]
    puts $log "LAYER_US = [mrd -value [dict get $addresses layer_us] $command_count]"
    set stage [dict get [print -dict test_stage] test_stage]
    set errors [dict get [print -dict test_errors] test_errors]
    if {$stage != 3 || $errors != 0} {error "INT8 inference verification failed"}
    source [file join $testdir layout.tcl]
    mrd -bin -file [file join $testdir board out0.bin] [dict get $addresses out0] 405
    mrd -bin -file [file join $testdir board out1.bin] [dict get $addresses out1] 1617
    puts $log "PASS: all 35 stages match the integer golden on three PS scheduled FPGA forwards; guards intact."
} message]} {
    catch {stop}
    puts $log "TEST ERROR: $message"
    set failed 1
}
foreach bp $breakpoints {catch {bpremove $bp}}
catch {disconnect}
close $log
exit $failed
