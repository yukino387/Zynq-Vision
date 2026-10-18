set_param general.maxThreads 16
set source_dir [file dirname [file normalize [info script]]]
set build_dir [file join $source_dir build]
set terminal_display [info exists ::env(VISION_HDMI_XDC)]
if {$terminal_display} {
    if {![file isfile $::env(VISION_HDMI_XDC)]} {error "VISION_HDMI_XDC must name a verified board-specific pin constraint file"}
    set build_dir [file join $source_dir build terminal]
}
create_project camera_cnn $build_dir -part xc7z020clg400-2 -force
set_property ip_repo_paths [file join $source_dir ../hls/build/conv/hls/impl/ip] [current_project]
update_ip_catalog
add_files [file join $source_dir ov5640_capture.v]
set_property XPM_LIBRARIES {XPM_FIFO} [current_project]
source [file join $source_dir base_system.tcl]
set ps [get_bd_cells processing_system7_0]
set accelerator_mhz [expr {$terminal_display ? 100.0 : 125.0}]
set_property CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ $accelerator_mhz $ps
set_property -dict [list CONFIG.PCW_ENET0_PERIPHERAL_ENABLE {1} CONFIG.PCW_ENET0_ENET0_IO {MIO 16 .. 27} CONFIG.PCW_ENET0_GRP_MDIO_ENABLE {1} CONFIG.PCW_ENET0_GRP_MDIO_IO {MIO 52 .. 53}] $ps
# QSPI boot uses the dedicated PS MIO pins; SD0 remains on MIO 40..45.
set_property -dict [list CONFIG.PCW_QSPI_PERIPHERAL_ENABLE {1} CONFIG.PCW_QSPI_QSPI_IO {MIO 1 .. 6} CONFIG.PCW_QSPI_GRP_SINGLE_SS_ENABLE {1} CONFIG.PCW_QSPI_GRP_FBCLK_ENABLE {1} CONFIG.PCW_QSPI_PERIPHERAL_FREQMHZ {200}] $ps
set_property CONFIG.NUM_MI 3 [get_bd_cells axi_smc]
set_property CONFIG.NUM_SI 3 [get_bd_cells smartconnect_0]
create_bd_cell -type module -reference ov5640_capture camera
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:2.0 camera_gpio
set_property -dict [list CONFIG.C_GPIO_WIDTH {5} CONFIG.C_ALL_OUTPUTS {1} CONFIG.C_IS_DUAL {1} CONFIG.C_GPIO2_WIDTH {4} CONFIG.C_ALL_INPUTS_2 {1}] [get_bd_cells camera_gpio]
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma:7.1 camera_dma
set_property -dict [list CONFIG.c_include_sg {0} CONFIG.c_include_mm2s {0} CONFIG.c_include_s2mm {1} CONFIG.c_s_axis_s2mm_tdata_width {32} CONFIG.c_m_axi_s2mm_data_width {32} CONFIG.c_sg_length_width {23} CONFIG.c_s2mm_burst_size {16}] [get_bd_cells camera_dma]
connect_bd_intf_net [get_bd_intf_pins axi_smc/M01_AXI] [get_bd_intf_pins camera_gpio/S_AXI]
connect_bd_intf_net [get_bd_intf_pins axi_smc/M02_AXI] [get_bd_intf_pins camera_dma/S_AXI_LITE]
connect_bd_intf_net [get_bd_intf_pins camera_dma/M_AXI_S2MM] [get_bd_intf_pins smartconnect_0/S02_AXI]
connect_bd_intf_net [get_bd_intf_pins camera/m_axis] [get_bd_intf_pins camera_dma/S_AXIS_S2MM]
connect_bd_net [get_bd_pins camera_gpio/gpio_io_o] [get_bd_pins camera/control]
connect_bd_net [get_bd_pins camera_gpio/gpio2_io_i] [get_bd_pins camera/status]
foreach pin {camera/clk camera_gpio/s_axi_aclk camera_dma/s_axi_lite_aclk camera_dma/m_axi_s2mm_aclk} {
    connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] [get_bd_pins $pin]
}
foreach pin {camera/resetn camera_gpio/s_axi_aresetn camera_dma/axi_resetn} {
    connect_bd_net [get_bd_pins rst_ps7_0_50M/peripheral_aresetn] [get_bd_pins $pin]
}
foreach name {cam_pclk cam_vsync cam_href cam_data cam_scl cam_sda cam_rst_n cam_pwdn} {
    make_bd_pins_external [get_bd_pins camera/$name]
    set_property name $name [get_bd_ports ${name}_0]
}
assign_bd_address -offset 0x41200000 -range 0x10000 -target_address_space [get_bd_addr_spaces processing_system7_0/Data] [get_bd_addr_segs camera_gpio/S_AXI/Reg] -force
assign_bd_address -offset 0x40400000 -range 0x10000 -target_address_space [get_bd_addr_spaces processing_system7_0/Data] [get_bd_addr_segs camera_dma/S_AXI_LITE/Reg] -force
assign_bd_address -offset 0x00000000 -range 0x40000000 -target_address_space [get_bd_addr_spaces camera_dma/Data_S2MM] [get_bd_addr_segs processing_system7_0/S_AXI_HP0/HP0_DDR_LOWOCM] -force
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] [get_bd_pins smartconnect_0/S02_ACLK]
connect_bd_net [get_bd_pins rst_ps7_0_50M/peripheral_aresetn] [get_bd_pins smartconnect_0/S02_ARESETN]
if {$terminal_display} {source [file join $source_dir ../display/integrate.tcl]}
validate_bd_design
set actual_frequency [get_property CONFIG.PCW_ACT_FPGA0_PERIPHERAL_FREQMHZ $ps]
if {abs($actual_frequency-$accelerator_mhz) > 0.001} {error "Unexpected actual FCLK frequency: $actual_frequency"}
puts "ACTUAL_FCLK_MHZ=$actual_frequency"
save_bd_design
set_property synth_checkpoint_mode None [get_files system.bd]
generate_target all [get_files system.bd]
set wrapper [make_wrapper -files [get_files system.bd] -top]
add_files $wrapper
add_files -fileset constrs_1 [file join $source_dir camera.xdc]
if {$terminal_display} {add_files -fileset constrs_1 [file normalize $::env(VISION_HDMI_XDC)]}
set_property top system_wrapper [current_fileset]
update_compile_order -fileset sources_1
synth_design -top system_wrapper -part xc7z020clg400-2
set clock_source [get_property SOURCE_PINS [get_clocks clk_fpga_0]]
set clock_pin [get_pins -hier -filter "NAME == $clock_source"]
create_clock -name clk_fpga_0 -period [expr {1000.0/$accelerator_mhz}] $clock_pin
write_checkpoint -force [file join $build_dir synthesized.dcp]
opt_design
write_checkpoint -force [file join $build_dir optimized.dcp]
place_design
phys_opt_design
route_design
if {$terminal_display} {phys_opt_design -hold_fix; route_design}
create_clock -name clk_fpga_0 -period [expr {1000.0/$accelerator_mhz}] $clock_pin
report_utilization -file [file join $build_dir utilization.rpt]
report_timing_summary -file [file join $build_dir timing.rpt]
report_bus_skew -file [file join $build_dir bus_skew.rpt]
write_checkpoint -force [file join $build_dir routed.dcp]
set timing [report_timing_summary -file [file join $build_dir timing.rpt] -return_string]
if {[string first {All user specified timing constraints are met.} $timing] < 0} {
    error "Camera accelerator timing qualification failed"
}
set skew [report_bus_skew -file [file join $build_dir bus_skew.rpt] -return_string]
if {[string first {VIOLATED} $skew] >= 0} {error "Camera FIFO bus-skew qualification failed"}
write_checkpoint -force [file join $build_dir qualified.dcp]
write_bitstream -force [file join $build_dir system_wrapper.bit]
write_hw_platform -fixed -force -file [file join $build_dir camera_cnn.xsa]
exit

