set workspace C:/00_workplace/fpga/cnn_accelerator/vitis_live
set root C:/00_workplace/fpga/cnn_accelerator
connect -url tcp:127.0.0.1:3121
configparams force-mem-accesses 1
if {[llength [targets -filter {name =~ "APU"}]] == 0} {
    targets -set 1
    catch {rst -system} msg
    after 1500
}
targets -set -filter {name =~ "APU"}
catch {rst -system} msg
after 1000
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
catch {stop}
source [file join $workspace camera_platform_live/export/camera_platform_live/hw/sdt/ps7_init.tcl]
ps7_init
targets -set -filter {name =~ "xc7z020"}
fpga -file [file join $root hardware/camera/build/system_wrapper.bit]
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
ps7_post_config
configparams force-mem-accesses 1
dow [file join $workspace camera_live/build/camera_live.elf]
puts "elf loaded"

proc rd {addr} { return [expr 0x[lindex [mrd $addr 1] end]] }
proc wr {addr value} { mwr $addr $value }

# registers
set BASE 0x43C00000
proc set_regs {ch_in ch_out fsize stride kernel act} {
    global BASE
    wr [expr {$BASE + 0x10}] 0x002CFC00
    wr [expr {$BASE + 0x18}] 0x002CFC00
    wr [expr {$BASE + 0x20}] 0x002CFC00
    wr [expr {$BASE + 0x28}] 0x002CFC00
    wr [expr {$BASE + 0x30}] 0x00C39FC0
    wr [expr {$BASE + 0x38}] 0x00C39FC0
    wr [expr {$BASE + 0x40}] 0x00C39FC0
    wr [expr {$BASE + 0x48}] 0x00C39FC0
    wr [expr {$BASE + 0x50}] 0x00C2A7C0
    wr [expr {$BASE + 0x58}] 0x00418C00
    wr [expr {$BASE + 0x60}] 0x00418C00
    wr [expr {$BASE + 0x68}] 0x00418C00
    wr [expr {$BASE + 0x70}] 0x00418C00
    wr [expr {$BASE + 0x78}] $ch_in
    wr [expr {$BASE + 0x80}] $ch_out
    wr [expr {$BASE + 0x88}] $fsize
    wr [expr {$BASE + 0x90}] $stride
    wr [expr {$BASE + 0x98}] $kernel
    wr [expr {$BASE + 0xA0}] $act
}
proc run_layer {name ch_in ch_out fsize stride kernel act} {
    global BASE
    set_regs $ch_in $ch_out $fsize $stride $kernel $act
    wr $BASE 0x0
    wr $BASE 0x1
    set done 0
    for {set i 0} {$i < 2000} {incr i} {
        if {[expr {[rd $BASE] & 2}]} { set done 1; break }
        after 1
    }
    puts "$name: ctrl=[format 0x%08X [rd $BASE]] done=$done"
}
run_layer "kernel1 1->8 224" 1 8 224 1 1 0
run_layer "kernel3s2 1->32 224" 1 32 224 2 3 1
run_layer "kernel3s1 8->8 224" 8 8 224 1 3 1
puts "final ctrl=[format 0x%08X [rd $BASE]]"
con
disconnect
