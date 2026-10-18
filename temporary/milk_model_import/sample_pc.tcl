connect -url tcp:127.0.0.1:3121
targets -set -filter {name =~ "ARM Cortex-A9 MPCore #0"}
for {set i 0} {$i < 6} {incr i} {
    stop
    puts "sample $i: [rrd pc] lr=[rrd lr]"
    con
    after 200
}
disconnect
