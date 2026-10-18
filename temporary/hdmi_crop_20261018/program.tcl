set root [file normalize [file join [file dirname [info script]] ../..]]
set bit [file join $root temporary/hdmi_crop_20261018/hardware-custom/system_wrapper.bit]
if {![file isfile $bit]} {error "Missing timing-qualified candidate bitstream"}
connect -url tcp:127.0.0.1:3121
targets -set -filter {name =~ "xc7z020"}
fpga -file $bit
puts HDMI-CANDIDATE-PROGRAMMED
disconnect
exit
