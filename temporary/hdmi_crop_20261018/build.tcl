set root [file normalize [file join [file dirname [info script]] ../..]]
set source_path [file join $root hardware/camera/build.tcl]
set fd [open $source_path r]
set body [read $fd]
close $fd
set body [string map [list \
    {set source_dir [file dirname [file normalize [info script]]]} "set source_dir [list [file join $root hardware/camera]]" \
    {set build_dir [file join $source_dir build terminal]} "set build_dir [list [file join $root temporary/hdmi_crop_20261018/hardware]]"] $body]
set ::env(VISION_HDMI_XDC) [file join $root hardware/display/navigator-v3.9.xdc]
eval $body
