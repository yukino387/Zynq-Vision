set root [file normalize [file join [file dirname [info script]] ../..]]
set build [file join $root temporary operator_pipeline_test build]
file mkdir $build
set variant optimized
if {[info exists ::env(HLS_VARIANT)]} {set variant $::env(HLS_VARIANT)}
open_project -reset [file join $build $variant]
set_top conv
set src [file join $root hardware hls src]
if {[info exists ::env(HLS_SOURCE)]} {set src $::env(HLS_SOURCE)}
foreach name {top std_conv pwconv maxpool upsample} {
    add_files [file join $src ${name}.cpp]
}
add_files -tb [file join $root temporary operator_pipeline_test test.cpp]
open_solution -reset solution -flow_target vivado
set_part xc7z020clg400-2
create_clock -period 10 -name default
config_interface -m_axi_addr64=false
csim_design
csynth_design
exit
