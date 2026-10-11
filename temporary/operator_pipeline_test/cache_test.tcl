set root [file normalize [file join [file dirname [info script]] ../..]]
set test [file join $root temporary weight_cache_test]
set flags "-I[file join $test mock] -I$root"
open_project -reset [file join $test build host]
set_top cache_probe
add_files [file join $test top.cpp]
foreach name {basic_conv basic_conv_weight resblock_body resblock_body_weight cspdarknet cspdarknet_weight yolo4_tiny yolo4_tiny_weight} {
    add_files [file join $root ${name}.cpp] -cflags $flags
}
add_files -tb [file join $test main.cpp] -cflags $flags
open_solution -reset solution -flow_target vivado
set_part xc7z020clg400-2
create_clock -period 10
csim_design
exit
