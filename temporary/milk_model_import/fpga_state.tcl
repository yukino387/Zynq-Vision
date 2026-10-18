connect -url tcp:127.0.0.1:3121
configparams force-mem-accesses 1
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
catch {stop}
puts "ctrl  = [mrd 0x43C00000 1]"
puts "gie   = [mrd 0x43C00004 1]"
puts "ier   = [mrd 0x43C00008 1]"
puts "isr   = [mrd 0x43C0000C 1]"
puts "in1   = [mrd 0x43C00010 1]"
puts "in2   = [mrd 0x43C00018 1]"
puts "in3   = [mrd 0x43C00020 1]"
puts "in4   = [mrd 0x43C00028 1]"
puts "w1    = [mrd 0x43C00030 1]"
puts "b     = [mrd 0x43C00050 1]"
puts "out1  = [mrd 0x43C00058 1]"
puts "ch_in = [mrd 0x43C00078 1]"
puts "ch_out= [mrd 0x43C00080 1]"
puts "fsize = [mrd 0x43C00088 1]"
puts "stride= [mrd 0x43C00090 1]"
puts "kernel= [mrd 0x43C00098 1]"
puts "act   = [mrd 0x43C000A0 1]"
con
disconnect
