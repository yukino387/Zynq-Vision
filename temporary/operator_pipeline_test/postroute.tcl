set base [file normalize [file join [file dirname [info script]] build]]
set variant $::env(HLS_VARIANT)
set stage [file join $base ${variant}_area_system_$::env(HLS_SYSTEM_MHZ) build]
open_checkpoint [file join $stage routed.dcp]
phys_opt_design -directive AggressiveExplore
route_design
report_utilization -file [file join $stage postroute_utilization.rpt]
report_timing_summary -file [file join $stage postroute_timing.rpt]
report_bus_skew -file [file join $stage postroute_bus_skew.rpt]
write_checkpoint -force [file join $stage postroute.dcp]
exit
