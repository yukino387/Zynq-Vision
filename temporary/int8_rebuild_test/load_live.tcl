set testdir {C:/00_workplace/fpga/cnn_accelerator/temporary/int8_rebuild_test/build}
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
    mwr 0xF8000008 0xDF0D
    mask_write 0xF8000170 0x03F03F30 0x00100800
    mwr 0xF8000004 0x767B
    targets -set -filter {name =~ "xc7z020"}
    fpga -file [file join $testdir qualified125 system_wrapper.bit]
    targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
    catch {stop}
    ps7_post_config
    configparams force-mem-accesses 1
    dow [file join $testdir live test.elf]
    con
} message]} {
    puts "TEST ERROR: $message"
    set failed 1
}

catch {disconnect}
exit $failed
