connect -url tcp:127.0.0.1:3121
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
catch {stop}
rst -system
after 500
source C:/00_workplace/fpga/cnn_accelerator/vitis_live/camera_platform_live/export/camera_platform_live/hw/sdt/ps7_init.tcl
ps7_init
ps7_post_config
configparams force-mem-accesses 1
dow C:/00_workplace/fpga/cnn_accelerator/temporary/zynq_ps_completion_20261016/qspi_probe.elf
con
after 1500
stop
puts [mrd 0x03000000 20]
disconnect
exit
