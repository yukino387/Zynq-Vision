set root [file normalize [file join [file dirname [info script]] ../..]]
set task [file join $root temporary/hdmi_crop_20261018]
set fd [open [file join $task build.tcl] r]
set wrapper [read $fd]
close $fd
set wrapper [string map [list {temporary/hdmi_crop_20261018/hardware} {temporary/hdmi_crop_20261018/hardware-custom}] $wrapper]
eval $wrapper
