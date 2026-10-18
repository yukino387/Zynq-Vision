connect -url tcp:127.0.0.1:3121
targets -set -filter {name == "APU"}
foreach a {0xf8890084 0xf800012c 0xf800014c 0xf8000150 0xf8000210} {puts [mrd -force $a]}
disconnect
exit
