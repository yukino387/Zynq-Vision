connect -url tcp:127.0.0.1:3121
targets -set -filter {name == "APU"}
puts "BOOT_MODE: [mrd -force 0xf800025c]"
puts "REBOOT_STATUS: [mrd -force 0xf8000258]"
puts "DEVCFG_STATUS: [mrd -force 0xf800700c]"
disconnect
exit
