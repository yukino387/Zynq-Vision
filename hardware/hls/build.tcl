set source_dir [file dirname [file normalize [info script]]]
open_project -reset [file join $source_dir build conv]
set_top conv
foreach name {top std_conv pwconv maxpool upsample} {
    add_files [file join $source_dir src ${name}.cpp]
}
open_solution -reset solution -flow_target vivado
set_part xc7z020clg400-2
create_clock -period 6 -name default
config_interface -m_axi_addr64=false
csynth_design
export_design -rtl verilog -format ip_catalog
exit
