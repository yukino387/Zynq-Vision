set testdir {C:/00_workplace/fpga/cnn_accelerator/temporary/int8_model_test/build}
set ready 0
set failed 0
if {[catch {
    connect -url tcp:127.0.0.1:3121
    targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
    catch {stop}
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
