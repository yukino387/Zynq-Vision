connect -url tcp:127.0.0.1:3121
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
puts "state: [state]"
catch {con} msg
puts "con: $msg"
puts "state-after: [state]"
disconnect
