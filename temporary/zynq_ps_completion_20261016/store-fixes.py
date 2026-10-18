from pathlib import Path
p=Path('camera/int8/live_main.cpp');s=p.read_text();s=s.replace('''            udp_send_status(status);usleep(100000);''','''            static XTime heartbeat=0;XTime now;XTime_GetTime(&now);
            if(now-heartbeat>=COUNTS_PER_SECOND){udp_send_status(status);heartbeat=now;}
            usleep(1000);''');p.write_text(s)
p=Path('camera/int8/model_store.cpp');s=p.read_text();s=s.replace('''        if(!writing||received!=total)result=6;''','''        if(verified && received==total) {} else if(!writing||received!=total)result=6;''');s=s.replace('''((model_available()&&!last_error)?8u:0u)''','''((model_available()&&!testing)?8u:0u)''');s=s.replace('''writing=false;verified=false;received=0;target=active==0?1:0;''','''writing=false;verified=false;received=0;last_error=0;target=active==0?1:0;''');p.write_text(s)
