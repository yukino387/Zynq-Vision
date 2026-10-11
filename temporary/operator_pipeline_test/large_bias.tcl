set root [file normalize [file join [file dirname [info script]] ../..]]
set test_dir [file join $root temporary operator_pipeline_test]
set variant $::env(HLS_VARIANT)
open_project -reset [file join $test_dir build ${variant}_bias_csim]
set_top conv
foreach name {top std_conv pwconv maxpool upsample} {
    add_files [file join $test_dir build ${variant}_src ${name}.cpp]
}
add_files -tb [file join $test_dir large_bias_test.cpp]
open_solution -reset solution -flow_target vivado
set_part xc7z020clg400-2
create_clock -period 6.667
csim_design
exit
