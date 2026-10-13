set testdir {C:/00_workplace/fpga/cnn_accelerator/temporary/int8_model_test/build}
set ready 0
set failed 0
if {[catch {
    connect -url tcp:127.0.0.1:3121
    targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
    catch {stop}
    source {C:/00_workplace/fpga/cnn_accelerator/vitis_live/camera_platform_live/export/camera_platform_live/hw/sdt/ps7_init.tcl}
    rst -system
    after 500
    ps7_init
    targets -set -filter {name =~ "xc7z020"}
    fpga -file [file join $testdir system_write build system_wrapper.bit]
    targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
    catch {stop}
    ps7_post_config
    configparams force-mem-accesses 1
    dow [file join $testdir live test.elf]
    set ready [bpadd -addr &test_load_ready -type hw]
    con -block -timeout 20
    bpremove $ready
    set ready 0
    source [file join $testdir live addresses.tcl]
    foreach name {weights metadata} {
        puts "Staging live $name"
        dow -data [file join $testdir $name.bin] [dict get $addresses $name]
    }
    con
} message]} {
    puts "TEST ERROR: $message"
    set failed 1
}
if {$ready} {catch {bpremove $ready}}
catch {disconnect}
exit $failed
