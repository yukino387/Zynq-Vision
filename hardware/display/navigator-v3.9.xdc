# Navigator V3.9 baseboard schematic sheets 4/5; ZYNQ core 2V5 sheets 3/7.
# Bank 35 is fitted for 3.3 V. Direct TMDS output; no external enable signal.
set_property PACKAGE_PIN G19 [get_ports {hdmi_data_p[0]}]
set_property PACKAGE_PIN G20 [get_ports {hdmi_data_n[0]}]
set_property PACKAGE_PIN K19 [get_ports {hdmi_data_p[1]}]
set_property PACKAGE_PIN J19 [get_ports {hdmi_data_n[1]}]
set_property PACKAGE_PIN J20 [get_ports {hdmi_data_p[2]}]
set_property PACKAGE_PIN H20 [get_ports {hdmi_data_n[2]}]
set_property PACKAGE_PIN J18 [get_ports hdmi_clk_p]
set_property PACKAGE_PIN H18 [get_ports hdmi_clk_n]
set_property IOSTANDARD TMDS_33 [get_ports {hdmi_data_p[*] hdmi_data_n[*] hdmi_clk_p hdmi_clk_n}]
# Video and accelerator exchange pixels/counters through explicit synchronizers/FIFO.
# Pixel and 5x serializer clocks remain timed together.
set_clock_groups -asynchronous -group [get_clocks clk_fpga_0] -group [get_clocks *system_display_clocks*]
