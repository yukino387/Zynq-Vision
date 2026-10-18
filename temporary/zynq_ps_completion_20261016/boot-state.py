from pathlib import Path
p=Path('camera/int8/live_main.cpp');s=p.read_text();s=s.replace('''    if(!camera_init() || !camera_udp_init()) return 1;
    model_store_init();
    CameraStatus status={0x31545343,0,0x7020,0,0,0,0,0,0,0,0,0};''','''    if(!camera_udp_init()) return 1;
    model_store_init();
    CameraStatus status={0x31545343,0,0x7020,0,0,0,0,0,0,0,0,0};
    while(!camera_init()) {
        status.errors=1;udp_pause();udp_send_status(status);
        while(!udp_running()){udp_poll();usleep(1000);}
    }''');s=s.replace('''if(!camera_set_brightness(udp_brightness())) { status.errors=1; udp_send_status(status); return 1; }''','''if(!camera_set_brightness(udp_brightness())) { status.errors=1; udp_send_status(status);udp_pause();continue; }''');p.write_text(s)
