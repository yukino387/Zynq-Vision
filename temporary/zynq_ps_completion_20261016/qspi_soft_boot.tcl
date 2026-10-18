connect -url tcp:127.0.0.1:3121
targets -set -filter {name == "APU"}
puts "BOOT_MODE: [mrd -force 0xf800025c]"
mwr -force 0xf8000008 0xdf0d
mwr -force 0xf8000200 1
after 1000
disconnect
exit
