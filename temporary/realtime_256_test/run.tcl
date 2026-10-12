set root [file normalize [file join [file dirname [info script]] ../..]]
set ::env(HLS_SHARED_CORE) 1
set ::env(HLS_INPUT256) 1
open_project -reset [file join $root temporary realtime_256_test build conv]
set_top conv
foreach name {top std_conv pwconv maxpool upsample} {
    add_files [file join $root hardware hls src ${name}.cpp]
}
add_files -tb [file join $root temporary operator_pipeline_test test.cpp]
open_solution -reset solution -flow_target vivado
set_part xc7z020clg400-2
create_clock -period 6
config_interface -m_axi_addr64=false
csim_design
csynth_design
export_design -rtl verilog -format ip_catalog
exit
