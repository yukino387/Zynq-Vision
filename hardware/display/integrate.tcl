# Called from the camera hardware builder only for a separate terminal build.
set display_source [file dirname [file normalize [info script]]]
add_files [glob [file join $display_source *.v]]
set_property CONFIG.PCW_EN_CLK1_PORT {1} $ps
set_property CONFIG.PCW_FPGA1_PERIPHERAL_FREQMHZ {100.000000} $ps
set_property -dict [list CONFIG.PCW_USB0_PERIPHERAL_ENABLE {1} CONFIG.PCW_USB0_USB0_IO {MIO 28 .. 39}] $ps
set_property CONFIG.NUM_MI 5 [get_bd_cells axi_smc]
create_bd_cell -type ip -vlnv xilinx.com:ip:clk_wiz:6.0 display_clocks
set_property -dict [list CONFIG.PRIM_IN_FREQ {100.000} CONFIG.CLKOUT1_REQUESTED_OUT_FREQ {74.250} CONFIG.CLKOUT2_USED {true} CONFIG.CLKOUT2_REQUESTED_OUT_FREQ {371.250} CONFIG.USE_RESET {false}] [get_bd_cells display_clocks]
connect_bd_net [get_bd_pins $ps/FCLK_CLK1] [get_bd_pins display_clocks/clk_in1]
create_bd_cell -type module -reference hdmi_scanout display_scanout
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_vdma:6.3 display_vdma
set_property -dict [list CONFIG.c_include_sg {0} CONFIG.c_include_mm2s {1} CONFIG.c_include_s2mm {0} CONFIG.c_m_axi_mm2s_data_width {64} CONFIG.c_m_axis_mm2s_tdata_width {32} CONFIG.c_num_fstores {2} CONFIG.c_mm2s_linebuffer_depth {4096} CONFIG.c_mm2s_genlock_mode {0}] [get_bd_cells display_vdma]
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_gpio:2.0 display_status
set_property -dict [list CONFIG.C_GPIO_WIDTH {32} CONFIG.C_ALL_INPUTS {1}] [get_bd_cells display_status]
connect_bd_intf_net [get_bd_intf_pins axi_smc/M03_AXI] [get_bd_intf_pins display_vdma/S_AXI_LITE]
connect_bd_intf_net [get_bd_intf_pins axi_smc/M04_AXI] [get_bd_intf_pins display_status/S_AXI]
set_property CONFIG.NUM_SI 3 [get_bd_cells smartconnect_3]
connect_bd_intf_net [get_bd_intf_pins display_vdma/M_AXI_MM2S] [get_bd_intf_pins smartconnect_3/S02_AXI]
connect_bd_intf_net [get_bd_intf_pins display_vdma/M_AXIS_MM2S] [get_bd_intf_pins display_scanout/s_axis]
foreach pin {display_scanout/axi_clk display_status/s_axi_aclk display_vdma/s_axi_lite_aclk display_vdma/m_axi_mm2s_aclk display_vdma/m_axis_mm2s_aclk smartconnect_3/S02_ACLK} {
    connect_bd_net [get_bd_pins $ps/FCLK_CLK0] [get_bd_pins $pin]
}
foreach pin {display_scanout/resetn display_status/s_axi_aresetn display_vdma/axi_resetn smartconnect_3/S02_ARESETN} {
    connect_bd_net [get_bd_pins rst_ps7_0_50M/peripheral_aresetn] [get_bd_pins $pin]
}
connect_bd_net [get_bd_pins display_clocks/clk_out1] [get_bd_pins display_scanout/pixel_clk]
connect_bd_net [get_bd_pins display_clocks/clk_out2] [get_bd_pins display_scanout/serial_clk]
connect_bd_net [get_bd_pins display_clocks/locked] [get_bd_pins display_scanout/locked]
connect_bd_net [get_bd_pins display_scanout/underflows] [get_bd_pins display_status/gpio_io_i]
foreach port {hdmi_data_p hdmi_data_n hdmi_clk_p hdmi_clk_n} {
    make_bd_pins_external [get_bd_pins display_scanout/$port]
    set_property name $port [get_bd_ports ${port}_0]
}
assign_bd_address -offset 0x43000000 -range 0x10000 -target_address_space [get_bd_addr_spaces $ps/Data] [get_bd_addr_segs display_vdma/S_AXI_LITE/Reg] -force
assign_bd_address -offset 0x41210000 -range 0x10000 -target_address_space [get_bd_addr_spaces $ps/Data] [get_bd_addr_segs display_status/S_AXI/Reg] -force
assign_bd_address -offset 0x00000000 -range 0x40000000 -target_address_space [get_bd_addr_spaces display_vdma/Data_MM2S] [get_bd_addr_segs $ps/S_AXI_HP3/HP3_DDR_LOWOCM] -force
