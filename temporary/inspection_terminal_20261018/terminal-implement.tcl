set_param general.maxThreads 16
set root [file normalize [file join [file dirname [info script]] ../..]]
set task [file join $root temporary/inspection_terminal_20261018]
set output [file join $root hardware/camera/build/terminal]
file delete -force [file join $task terminal-vivado.PASS]
open_checkpoint [file join $output optimized.dcp]
set parent system_i/display_scanout/inst
set counter [get_cells -hier -regexp {.*display_scanout/inst/failures_reg\[0\]$}]
if {[llength $counter]!=1 || [get_property REF_NAME $counter] ne "FDRE"} {error "Unexpected diagnostic counter implementation"}
set clock [get_nets -of_objects [get_pins -of_objects $counter -filter {REF_PIN_NAME == C}]]
set reset [get_nets -of_objects [get_pins -of_objects $counter -filter {REF_PIN_NAME == R}]]
puts "GRAY_REGISTER_CLOCK=$clock RESET=$reset"
set enable [create_cell -reference VCC $parent/gray_enable]
set enabled [create_net $parent/gray_enabled]
connect_net -net $enabled -objects [get_pins -of_objects $enable -filter {REF_PIN_NAME == P}]
for {set bit 0} {$bit<32} {incr bit} {
    set sync [get_cells -hier -regexp [format {.*display_scanout/inst/sync1_reg\[%d\]$} $bit]]
    if {[llength $sync]!=1} {error "Missing diagnostic synchronizer bit $bit"}
    set destination [get_pins -of_objects $sync -filter {REF_PIN_NAME == D}]
    set original [get_nets -of_objects $destination]
    set reg [create_cell -reference FDRE [format {%s/gray_failures_reg[%d]} $parent $bit]]
    set_property INIT 1'b0 $reg
    disconnect_net -net $original -objects $destination
    connect_net -net $original -objects [get_pins -of_objects $reg -filter {REF_PIN_NAME == D}]
    connect_net -net $clock -objects [get_pins -of_objects $reg -filter {REF_PIN_NAME == C}]
    connect_net -net $reset -objects [get_pins -of_objects $reg -filter {REF_PIN_NAME == R}]
    connect_net -net $enabled -objects [get_pins -of_objects $reg -filter {REF_PIN_NAME == CE}]
    set registered [create_net [format {%s/registered_gray[%d]} $parent $bit]]
    connect_net -net $registered -objects [concat $destination [get_pins -of_objects $reg -filter {REF_PIN_NAME == Q}]]
}
set_property ASYNC_REG TRUE [get_cells -hier -regexp {.*display_scanout/inst/reset_pipe_reg\[[0-9]+\]$}]
set source [get_property SOURCE_PINS [get_clocks clk_fpga_0]]
create_clock -name clk_fpga_0 -period 10.000 [get_pins -hier -filter "NAME == $source"]
read_xdc [file join $root hardware/display/navigator-v3.9.xdc]
opt_design
write_checkpoint -force [file join $task terminal-optimized.dcp]
place_design
phys_opt_design
route_design
phys_opt_design -hold_fix
route_design
report_utilization -file [file join $output utilization.rpt]
set timing [report_timing_summary -file [file join $output timing.rpt] -return_string]
set skew [report_bus_skew -file [file join $output bus_skew.rpt] -return_string]
write_checkpoint -force [file join $output terminal-routed.dcp]
if {[string first {All user specified timing constraints are met.} $timing] < 0} {error "Terminal timing qualification failed"}
if {[string first {VIOLATED} $skew] >= 0} {error "Terminal FIFO bus skew qualification failed"}
write_checkpoint -force [file join $output qualified.dcp]
write_bitstream -force [file join $output system_wrapper.bit]
set marker [open [file join $task terminal-vivado.PASS] w]
puts $marker "100 MHz terminal bitstream timing qualified; video CDC registered and constrained"
close $marker
exit
