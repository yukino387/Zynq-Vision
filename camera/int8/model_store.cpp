#include "model_store.h"
#include "sha256.h"
#include "ff.h"
#include "xil_cache.h"
#include "xil_printf.h"
#include <cstring>
extern "C" {
int8_t weights[weight_bytes] __attribute__((aligned(64)));
int32_t metadata[metadata_words] __attribute__((aligned(64)));
}
namespace {
constexpr uint32_t total=128+weight_bytes+4*metadata_words;
constexpr unsigned slot_count=16;
// 槽位文件名固定两位数字，8.3 安全，不依赖 LFN 配置。
void slot_path(char* path,unsigned slot) {
    path[0]='0';path[1]=':';path[2]='/';path[3]='M';
    path[4]=char('0'+slot/10);path[5]=char('0'+slot%10);
    path[6]='.';path[7]='B';path[8]='I';path[9]='N';path[10]='\0';
}
const char* const active_path="0:/ACTIVE.BIN";
// ACTIVE.BIN 是"哪个槽在跑"的持久记录，只在自检通过后写；它坏了不影响启动，
// 启动会退回去扫描槽位头。crc32 覆盖前 124 字节。
struct ActiveRecord {
    uint32_t magic, active, previous, generation;
    uint8_t pad[108];
    uint32_t crc32;
};
static_assert(sizeof(ActiveRecord)==128,"Active record size");
constexpr uint32_t active_magic=0x31544341;
constexpr uint32_t no_slot=0xffffffffu;
FATFS fs; FIL upload; FIL file;
bool mounted=false, writing=false, verified=false, testing=false, activate=false, boot_test=false;
int active=-1, previous=-1, target=-1, commit_target=-1, commit_previous=-1, select_request=-1;
uint32_t received=0, last_error=0, sd_result=0, generation=0, slot_total=0;
ModelHeader current={}, staged={}, slots[slot_count]={};
bool present[slot_count]={};
// 64 字节对齐：SD 驱动按范围把数据 DMA 进这个缓冲区并自己做缓存失效。
// 不要在这里加 flush —— 那会把 DMA 之前留在缓存里的旧数据写回去、盖掉刚读到的载荷。
uint8_t staging[weight_bytes+4*metadata_words] __attribute__((aligned(64)));
uint32_t crc(const void* p,unsigned n) {
    uint32_t value=0xffffffff;const uint8_t* b=static_cast<const uint8_t*>(p);
    while(n--){value^=*b++;for(unsigned k=0;k<8;++k)value=(value>>1)^(0xedb88320u&uint32_t(-int(value&1)));}return ~value;
}
bool header_valid(const ModelHeader& h) {
    return h.magic==0x314e4e43 && h.format==1 && h.weight_size==weight_bytes && h.metadata_size==4*metadata_words && h.version[0] && std::memchr(h.version,0,64) && !h.reserved && h.crc32==crc(&h,120);
}
// 读一个包文件并校验：结构头、payload SHA256、图模板。命中则 staging 里就是可用的权重+偏置。
bool load_file(const char* path,ModelHeader& h) {
    UINT n=0;
    if(f_open(&file,path,FA_READ)!=FR_OK)return false;
    bool ok=f_size(&file)==total && f_read(&file,&h,sizeof(h),&n)==FR_OK && n==sizeof(h) && header_valid(h);
    if(ok)ok=f_lseek(&file,128)==FR_OK;
    Sha256 sha;
    for(unsigned offset=0;ok && offset<sizeof(staging);) {
        const unsigned count=sizeof(staging)-offset<65536?sizeof(staging)-offset:65536;
        ok=f_read(&file,staging+offset,count,&n)==FR_OK && n==count;
        if(ok)sha.update(staging+offset,count);
        offset+=count;
    }
    f_close(&file);uint8_t digest[32];sha.finish(digest);
    if(!ok || std::memcmp(digest,h.sha256,32))return false;
    const int32_t* graph=reinterpret_cast<const int32_t*>(staging+weight_bytes);
    for(unsigned word=0;word<command_count*10;++word) {
        if(word==4) {if(graph[word]!=1 && graph[word]!=3)return false;}
        else if(graph[word]!=commands[word])return false;
    }
    return true;
}
bool load_slot(unsigned slot,ModelHeader& h){char path[11];slot_path(path,slot);return load_file(path,h)&&h.committed==1;}
// 只看 128 字节头，不读载荷；目录就是靠扫这 16 个头得到的，不维护独立索引文件。
bool read_slot_header(unsigned slot,ModelHeader& h) {
    char path[11];slot_path(path,slot);UINT n=0;
    if(f_open(&file,path,FA_READ)!=FR_OK)return false;
    const bool ok=f_size(&file)==total && f_read(&file,&h,sizeof(h),&n)==FR_OK && n==sizeof(h) && header_valid(h) && h.committed==1;
    f_close(&file);return ok;
}
void refresh() {
    slot_total=0;
    for(unsigned slot=0;slot<slot_count;++slot) {
        ModelHeader h={};
        present[slot]=read_slot_header(slot,h);
        slots[slot]=present[slot]?h:ModelHeader{};
        if(present[slot])++slot_total;
    }
}
// 空槽 = 没有有效 committed 头。当前版本和上一版一定 present，所以不会被选中。
int free_slot(){for(unsigned slot=0;slot<slot_count;++slot)if(!present[slot])return int(slot);return -1;}
// 提交点在这里：自检通过后才有 committed 头，半截的下载文件因此永远不被当成模型。
bool commit_slot(unsigned slot,ModelHeader& h) {
    char path[11];slot_path(path,slot);UINT n=0;
    h.committed=1;h.generation=generation+1;h.crc32=crc(&h,120);
    if(f_open(&file,path,FA_WRITE)!=FR_OK)return false;
    const bool ok=f_write(&file,&h,sizeof(h),&n)==FR_OK && n==sizeof(h) && f_sync(&file)==FR_OK;
    f_close(&file);
    if(ok){if(!present[slot])++slot_total;present[slot]=true;slots[slot]=h;}
    return ok;
}
bool read_active(ActiveRecord& r) {
    UINT n=0;
    if(f_open(&file,active_path,FA_READ)!=FR_OK)return false;
    const bool ok=f_read(&file,&r,sizeof(r),&n)==FR_OK && n==sizeof(r);
    f_close(&file);return ok && r.magic==active_magic && r.crc32==crc(&r,124);
}
bool write_active(unsigned slot,unsigned prev,uint32_t value) {
    ActiveRecord r={};r.magic=active_magic;r.active=slot;r.previous=prev;r.generation=value;r.crc32=crc(&r,124);
    UINT n=0;
    if(f_open(&file,active_path,FA_CREATE_ALWAYS|FA_WRITE)!=FR_OK)return false;
    const bool ok=f_write(&file,&r,sizeof(r),&n)==FR_OK && n==sizeof(r) && f_sync(&file)==FR_OK;
    f_close(&file);return ok;
}
void copy_model() {
    std::memcpy(weights,staging,weight_bytes);
    std::memcpy(metadata,staging+weight_bytes,4*metadata_words);
    Xil_DCacheFlushRange((INTPTR)weights,weight_bytes);
    Xil_DCacheFlushRange((INTPTR)metadata,4*metadata_words);
}
}
void model_store_init() {
    sd_result=f_mount(&fs,"0:/",1);mounted=sd_result==FR_OK;
    if(!mounted){last_error=3;xil_printf("SD mount failed; card is not formatted automatically\r\n");return;}
    refresh();
    ActiveRecord r={};const bool known=read_active(r);
    // 激活计数取 ACTIVE.BIN 和槽位头里较大的那个，指针丢了也不会让计数倒退。
    uint32_t recorded=0;
    for(unsigned slot=0;slot<slot_count;++slot)if(slots[slot].generation>recorded)recorded=slots[slot].generation;
    if(known&&r.generation>recorded)recorded=r.generation;
    // 优先 ACTIVE.BIN 记的当前槽，其次上一版槽，最后退回任意有效槽（指针丢了或卡被换过）。
    int order[slot_count+2],count=0;
    if(known&&r.active<slot_count)order[count++]=int(r.active);
    if(known&&r.previous<slot_count&&int(r.previous)!=(count?order[0]:-1))order[count++]=int(r.previous);
    for(unsigned slot=0;slot<slot_count;++slot) {
        bool seen=false;
        for(int i=0;i<count;++i)if(order[i]==int(slot))seen=true;
        if(!seen)order[count++]=int(slot);
    }
    for(int i=0;i<count;++i) {
        const unsigned slot=unsigned(order[i]);ModelHeader h={};
        if(!load_slot(slot,h))continue;
        copy_model();current=h;active=int(slot);
        previous=-1;
        for(int j=0;j<count;++j)
            if(order[j]!=int(slot)&&present[order[j]]){previous=order[j];break;}
        generation=recorded;
        testing=true;boot_test=true;last_error=0;
        xil_printf("SD model: %s slot %u generation %u\r\n",h.version,slot,generation);
        return;
    }
    last_error=6;xil_printf("SD has no valid committed model; waiting for upload\r\n");
}
bool model_available(){return active>=0;}
bool model_test_pending(){return testing;}
void model_service() {
    // 库内快切的 SD 读 + SHA256 放在主循环，不放在 UDP 路径上：
    // udp_poll() 是在 forward() 内层被调的，在这里做秒级 IO 会顶到 2 秒看门狗。
    if(select_request>=0) {
        const unsigned slot=unsigned(select_request);select_request=-1;
        ModelHeader h={};
        if(!load_slot(slot,h)){last_error=7;return;}
        staged=h;commit_target=int(slot);activate=true;
    }
    if(!activate)return;
    activate=false;previous=commit_previous;copy_model();testing=true;
}
void model_complete_test(bool passed) {
    if(!testing)return;
    testing=false;
    if(boot_test){boot_test=false;last_error=passed?0:7;if(!passed)active=-1;return;}
    const int slot=commit_target,fallback=commit_previous;
    if(slot>=0&&passed&&commit_slot(unsigned(slot),staged)&&write_active(unsigned(slot),fallback<0?no_slot:unsigned(fallback),generation+1)) {
        generation++;active=slot;previous=fallback;current=staged;last_error=0;verified=false;return;
    }
    // 自检没过，或者过了但落盘失败：都不许把没落盘的模型说成"已激活"，退回上一版。
    last_error=passed?3:7;verified=false;
    ModelHeader h={};
    if(fallback>=0&&load_slot(unsigned(fallback),h)){copy_model();current=h;active=fallback;}else active=-1;
    previous=-1;
}
ModelReply model_request(uint32_t request,uint32_t operation,uint32_t offset,const uint8_t* data,uint32_t size) {
    uint32_t result=0;
    // op7 只读槽位头，自检期间也放行，否则平台提交完立刻拉清单会撞上忙。
    if(operation && !mounted)result=3;
    else if(operation && operation!=7 && (testing||activate||select_request>=0))result=2;
    else if(operation==1) {
        // 库满在这里就拒，不让客户端白传 6 MB。就地写进空槽，不走临时文件改名
        // （FatFs 的 f_rename 是先注册新目录项再删旧的，断电会留下两个名字共用一条簇链）。
        const int slot=free_slot();
        if(size||offset)result=1;
        else if(slot<0)result=5;
        else {char path[11];slot_path(path,unsigned(slot));
            if(writing)f_close(&upload);
            writing=false;verified=false;received=0;select_request=-1;
            if(f_open(&upload,path,FA_CREATE_ALWAYS|FA_WRITE)!=FR_OK)result=3;
            else {writing=true;target=slot;}}
    } else if(operation==2) {
        if(!writing||!size||size>1400||offset>total||size>total-offset)result=1;
        // offset<=received 都接受并 seek 回去重写，重传因此是幂等的；有空洞就拒。
        else if(offset>received)result=1;
        else {UINT n=0;
            if(f_lseek(&upload,offset)!=FR_OK||f_write(&upload,data,size,&n)!=FR_OK||n!=size)result=3;
            else if(offset+size>received)received=offset+size;}
    } else if(operation==3) {
        if(verified && received==total) {} else if(!writing||received!=total)result=6;
        else {const FRESULT sync=f_sync(&upload);f_close(&upload);writing=false;
            if(sync!=FR_OK)result=3;
            else {char path[11];slot_path(path,unsigned(target));
                if(!load_file(path,staged))result=4;else verified=true;}}
    } else if(operation==4) {
        // 包已经躺在槽里且校验过，这里只登记待激活，真正的落盘在自检通过之后。
        if(!verified||target<0)result=6;
        else {received=0;commit_target=target;commit_previous=active;activate=true;}
    } else if(operation==5) {
        // 回滚到上一版；成功后当前版本反过来成为上一版，所以这里是一次交换。
        if(previous<0||!present[previous])result=6;else {select_request=previous;commit_previous=active;}
    } else if(operation==6) {
        if(writing)f_close(&upload);
        writing=false;verified=false;received=0;select_request=-1;commit_previous=-1;
    } else if(operation==7) {
        if(offset>=slot_count)result=1;
    } else if(operation==8) {
        // 选中的就是当前版本时不做任何事，让客户端的轮询直接看到"已经是要的那个"。
        if(offset>=slot_count||!present[offset])result=6;
        else if(int(offset)!=active){select_request=int(offset);commit_previous=active;}
    } else if(operation==9) {
        if(offset>=slot_count||!present[offset])result=6;
        else if(int(offset)==active||int(offset)==previous)result=8;
        else {char path[11];slot_path(path,unsigned(offset));
            if(f_unlink(path)!=FR_OK)result=3;
            else {present[offset]=false;slots[offset]=ModelHeader{};--slot_total;}}
    } else if(operation!=0)result=1;
    if(operation && result)last_error=result;
    uint32_t reply_received=received,reply_total=total,reply_generation=generation;
    // 忙位按操作之后的状态报，客户端提交完立刻轮询 op0 时要能看到自检已经起来了。
    uint32_t flags=(mounted?1u:0u)|(model_available()?2u:0u)|(verified?4u:0u)|((model_available()&&!testing)?8u:0u)
                  |((testing||activate||select_request>=0)?16u:0u)|((last_error&0xffu)<<16)|((sd_result&0xffu)<<8);
    char version[64];std::memcpy(version,current.version,64);
    uint8_t digest[32];std::memcpy(digest,current.sha256,32);
    if(!result&&operation==0){reply_received=active<0?no_slot:uint32_t(active);reply_total=slot_count;}
    else if(!result&&operation==7){reply_received=offset;reply_total=slot_total;reply_generation=0;std::memset(version,0,64);std::memset(digest,0,32);
        if(present[offset]){std::memcpy(version,slots[offset].version,64);std::memcpy(digest,slots[offset].sha256,32);reply_generation=slots[offset].generation;
            if(int(offset)==active)flags|=0x20u;
            if(int(offset)==previous)flags|=0x40u;}}
    ModelReply reply={0x3152444d,request,result,reply_received,reply_total,reply_generation,flags,{}, {}};
    std::memcpy(reply.version,version,64);std::memcpy(reply.sha256,digest,32);return reply;
}
