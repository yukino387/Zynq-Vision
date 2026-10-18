from pathlib import Path
p=Path('camera/udp_output.cpp');s=p.read_text();s=s.replace('#include "udp_output.h"','#include "udp_output.h"\n#include "int8/model_store.h"')
s=s.replace('''    if (packet && packet->tot_len == 1) {''','''    if (packet && packet->tot_len >= 20 && packet->tot_len <= 1420) {
        uint8_t bytes[1420];
        pbuf_copy_partial(packet,bytes,packet->tot_len,0);
        uint32_t header[5];std::memcpy(header,bytes,20);
        if(header[0]==0x314c444d && header[4]==packet->tot_len-20) {
            const bool owner=peer_port==port && ip_addr_cmp(&peer,address);
            ModelReply reply={};
            if(header[2]==0 || owner)reply=model_request(header[1],header[2],header[3],bytes+20,header[4]);
            else {reply.magic=0x3152444d;reply.request=header[1];reply.result=2;}
            pbuf* response=pbuf_alloc(PBUF_TRANSPORT,sizeof(reply),PBUF_RAM);
            if(response){std::memcpy(response->payload,&reply,sizeof(reply));udp_sendto(socket,response,address,port);pbuf_free(response);}
        }
    } else if (packet && packet->tot_len == 1) {''')
s=s.replace('bool udp_running() { return running; }','bool udp_running() { return running; }\nvoid udp_pause() { running=false; }')
p.write_text(s)
p=Path('camera/udp_output.h');s=p.read_text().replace('bool udp_running();','bool udp_running();\nvoid udp_pause();');p.write_text(s)
p=Path('camera/int8/weights.S');p.write_text('''.section .rodata
.balign 64
.global commands
.type commands, %object
commands:
.incbin "C:/00_workplace/fpga/cnn_accelerator/camera/int8/metadata.bin", 0, 1320
.size commands, .-commands
.section .note.GNU-stack,"",%progbits
''')
p=Path('camera/int8/live_main.cpp');s=p.read_text();s=s.replace('#include "model.h"','#include "model.h"\n#include "model_store.h"')
s=s.replace('extern const int8_t weights[];\nextern const int32_t metadata[];\n','')
s=s.replace('uint32_t& transfer_us) {','uint32_t& transfer_us,bool& transmission_failed) {')
s=s.replace('if(!udp_send_frame(frame,2,pixels[current],CAMERA_BYTES)) return 3;','if(!udp_send_frame(frame,2,pixels[current],CAMERA_BYTES)) transmission_failed=true;')
s=s.replace('    while(!udp_client_ready()) udp_poll();','    model_store_init();')
s=s.replace('''        while(!udp_running()) { udp_poll(); usleep(1000); }''','''        model_service();
        while((!udp_running() || !model_available()) && !model_test_pending()) {
            udp_poll(); model_service();
            status.errors=model_available()?status.errors:5;
            udp_send_status(status);usleep(100000);
        }''')
s=s.replace('const bool inference=!udp_camera_only();','const bool inference=!udp_camera_only() || model_test_pending();')
s=s.replace('const bool preview=udp_preview_enabled();','const bool preview=udp_client_ready() && udp_preview_enabled();')
s=s.replace('''            status.errors=2; udp_send_status(status); return 2;''','''            status.errors=2; model_complete_test(false); udp_send_status(status); udp_pause();
            frame_captured=false;pending=false;armed=false;prepared_rows=0;continue;''')
s=s.replace('''if(!armed && !camera_begin(pixels[1-current])) { status.errors=2; udp_send_status(status); return 2; }''','''if(!armed && !camera_begin(pixels[1-current])) { status.errors=2;model_complete_test(false);udp_send_status(status);udp_pause();frame_captured=false;pending=false;armed=false;prepared_rows=0;continue; }''')
s=s.replace('''        const unsigned error=inference ? forward(engine,current,frame,preview,pending,armed,prepared_rows,conversion_us,transfer_us) : 0;
        if(error) { status.errors=error; udp_send_status(status); return error; }''','''        bool transmission_failed=false;
        const unsigned error=inference ? forward(engine,current,frame,preview,pending,armed,prepared_rows,conversion_us,transfer_us,transmission_failed) : 0;
        model_complete_test(!error);
        if(error) { status.errors=error; udp_send_status(status);udp_pause();frame_captured=false;pending=false;armed=false;prepared_rows=0;continue; }''')
s=s.replace('''        if((inference && (!udp_send_frame(frame,0,out0,1617) ||''','''        if(udp_client_ready() && ((inference && (!udp_send_frame(frame,0,out0,1617) ||''')
s=s.replace('''(!inference && preview && !udp_send_frame(frame,2,pixels[current],CAMERA_BYTES))) {
            status.errors=3; udp_send_status(status); return 3;
        }''','''(!inference && preview && !udp_send_frame(frame,2,pixels[current],CAMERA_BYTES)))) transmission_failed=true;
        status.errors=transmission_failed?3:0;''')
p.write_text(s)
p=Path('camera/int8/model_store.cpp');s=p.read_text();s=s.replace('verified=false, testing=false, activate=false;','verified=false, testing=false, activate=false, boot_test=false;')
s=s.replace('active=slot;last_error=0;xil_printf','active=slot;target=slot;previous=slot;testing=true;boot_test=true;last_error=0;xil_printf')
s=s.replace('''    testing=false;
    if(passed)''','''    testing=false;
    if(boot_test){boot_test=false;last_error=passed?0:7;if(!passed)active=-1;return;}
    if(passed)''')
p.write_text(s)
p=Path('camera/create_app.py');s=p.read_text();s=s.replace('domain.set_lib(lib_name="lwip220")','domain.set_lib(lib_name="lwip220")\ndomain.set_lib(lib_name="xilffs")')
s=s.replace('"model.h", "weights.S"','"model.h", "weights.S", "model_store.cpp", "model_store.h", "sha256.h"')
s=s.replace('root / "camera/int8/weights.S", root / "camera/camera_input.cpp"','root / "camera/int8/weights.S", root / "camera/int8/model_store.cpp", root / "camera/camera_input.cpp"')
p.write_text(s)
