open_project C:/00_workplace/vivado/cnn_accelerator/cnn_accelerator.xpr
open_bd_design [get_files system.bd]
write_bd_tcl -force C:/00_workplace/fpga/cnn_accelerator/hardware/camera/base_system.tcl
puts "CAMERA_BASELINE_CELLS [get_bd_cells]"
puts "CAMERA_CLOCK [get_property CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ [get_bd_cells processing_system7_0]]"
puts "CAMERA_GPIO [get_property CONFIG.PCW_GPIO_EMIO_GPIO_ENABLE [get_bd_cells processing_system7_0]]"
puts "CAMERA_GPIO_WIDTH [get_property CONFIG.PCW_GPIO_EMIO_GPIO_IO [get_bd_cells processing_system7_0]]"
close_project
exit
