from pathlib import Path
root=Path(__file__).resolve().parents[2]
test=Path(__file__).resolve().parent
s=(root/'camera/int8/live_main.cpp').read_text().replace('#include "model.h"','#include "camera/int8/model.h"').replace('#include "gray.h"','#include "camera/int8/gray.h"')
s=s.replace('extern "C" {','extern "C" {\nvolatile uint32_t live_cpu[9] __attribute__((aligned(64)));\nvolatile uint32_t live_layer_us[33] __attribute__((aligned(64)));\nvolatile uint32_t live_poll_window_us[33] __attribute__((aligned(64)));')
s=s.replace('    Xil_DCacheFlushRange((INTPTR)features,224*256);','    for(unsigned i=2;i<9;++i) live_cpu[i]=0;\n    XTime flush_begin,flush_end;\n    XTime_GetTime(&flush_begin);\n    Xil_DCacheFlushRange((INTPTR)features,224*256);\n    XTime_GetTime(&flush_end);\n    live_cpu[7]=microseconds(flush_end-flush_begin);')
s=s.replace('        const int32_t* c=', '        XTime setup_begin,setup_end,layer_begin,layer_end,last_not_done;\n        XTime_GetTime(&setup_begin);\n        const int32_t* c=')
s=s.replace('        XConv_Start(&engine);','        XTime_GetTime(&setup_end);\n        live_cpu[4]+=microseconds(setup_end-setup_begin);\n        XTime_GetTime(&layer_begin);\n        last_not_done=layer_begin;\n        XConv_Start(&engine);')
s=s.replace('        while(!XConv_IsDone(&engine)) {','        for(;;) {\n            XTime poll_begin;\n            XTime_GetTime(&poll_begin);\n            if(XConv_IsDone(&engine)) break;\n            last_not_done=poll_begin;')
s=s.replace('                if(!camera_finish(pixels[1-current]))', '                XTime capture_begin,capture_end;\n                XTime_GetTime(&capture_begin);\n                if(!camera_finish(pixels[1-current]))')
s=s.replace('                pending=false;','                XTime_GetTime(&capture_end);\n                live_cpu[8]=microseconds(capture_end-capture_begin);\n                pending=false;')
s=s.replace('conversion_us+=microseconds(work_end-work_begin);','conversion_us+=microseconds(work_end-work_begin);\n                live_cpu[prepared_rows<=416?2:3]+=microseconds(work_end-work_begin);')
s=s.replace('        }\n    }\n    Xil_DCacheInvalidateRange','        }\n        XTime_GetTime(&layer_end);\n        live_layer_us[layer]=microseconds(layer_end-layer_begin);\n        live_poll_window_us[layer]=microseconds(layer_end-last_not_done);\n        live_cpu[6]+=live_poll_window_us[layer];\n    }\n    XTime head_begin,head_end;\n    XTime_GetTime(&head_begin);\n    Xil_DCacheInvalidateRange')
s=s.replace('    return 0;\n}\n\nint main()','    XTime_GetTime(&head_end);\n    live_cpu[5]=microseconds(head_end-head_begin);\n    Xil_DCacheFlushRange((INTPTR)live_cpu,sizeof(live_cpu));\n    Xil_DCacheFlushRange((INTPTR)live_layer_us,sizeof(live_layer_us));\n    Xil_DCacheFlushRange((INTPTR)live_poll_window_us,sizeof(live_poll_window_us));\n    return 0;\n}\n\nint main()')
s=s.replace('        if(!camera_begin(pixels[1-current]))','        XTime camera_begin_time,camera_end_time;\n        XTime_GetTime(&camera_begin_time);\n        if(!camera_begin(pixels[1-current]))')
s=s.replace('        pending=true;', '        XTime_GetTime(&camera_end_time);\n        live_cpu[0]=microseconds(camera_end_time-camera_begin_time);\n        pending=true;\n        XTime input_begin,input_end;\n        XTime_GetTime(&input_begin);')
s=s.replace('        XTime_GetTime(&converted);', '        XTime_GetTime(&input_end);\n        live_cpu[1]=microseconds(input_end-input_begin);\n        XTime_GetTime(&converted);')
(test/'build/live_main.cpp').write_bytes(s.encode())
