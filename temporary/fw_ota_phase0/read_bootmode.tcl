connect -url tcp:127.0.0.1:3121
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
catch {stop}
puts "BOOT_MODE_REG_RAW=[mrd 0xF800025C]"
con
disconnect
exit
