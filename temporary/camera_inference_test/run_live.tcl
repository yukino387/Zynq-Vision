set testdir [file dirname [file normalize [info script]]]
set root [file normalize [file join $testdir ../..]]
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
dow [file join $testdir build/camera_live.elf]
set ready [bpadd -addr &test_load_ready -type hw]
con -block -timeout 20
bpremove $ready
source [file join $testdir build/camera_live-addresses.tcl]
foreach {name file} {raw_files all_weights.bin pc_directory directory.bin} {
    dow -data [file join $root temporary/full_weight_test/pc_files $file] [dict get $addresses $name]
}
con
disconnect
exit
