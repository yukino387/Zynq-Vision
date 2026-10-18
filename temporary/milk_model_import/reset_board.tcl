connect -url tcp:127.0.0.1:3121
puts "before: [targets]"
targets -set 1
catch {stop} m1
puts "stop: $m1"
catch {rst -system} m2
puts "system: $m2"
catch {rst -processor} m3
puts "processor: $m3"
catch {rst -cores} m4
puts "cores: $m4"
after 2000
puts "after: [targets]"
disconnect
