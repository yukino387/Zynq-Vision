connect -url tcp:127.0.0.1:3121
puts [targets]
targets -set -filter {name =~ "DAP*"}
catch {rst -system} e
puts "reset: $e"
after 500
puts [targets]
disconnect
exit
