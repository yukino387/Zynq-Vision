connect -url tcp:127.0.0.1:3121
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
catch {stop}
puts "BOOT_MODE: [mrd 0xf800025c]"
puts "REBOOT_STATUS: [mrd 0xf8000258]"
puts [rrd pc]
puts [rrd lr]
puts [bt]
con
disconnect
exit

