#include "hardware.h"
#include "core.h"
#include "linux/vision_uapi.h"
#include "model_graph.h"
#include "../int8/model.h"
#include "../int8/gray.h"
#include "../../hardware/camera/ov5640_registers.h"
#include "../../hardware/camera/ov5640_mode.h"
#include <atomic>
#include <arm_neon.h>
#include <algorithm>
#include <chrono>
#include <cstring>
#include <future>
#include <stdexcept>
#include <thread>
#include <fcntl.h>
#include <sched.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>

namespace terminal {
static constexpr unsigned metadata_offset=weight_bytes,feature_offset=(weight_bytes+metadata_words*4+63)&~63u;
static constexpr unsigned pixels_offset=(feature_offset+feature_bytes+63)&~63u;
static constexpr unsigned camera_bytes=416*416*2;
static uint64_t clock_ns() { return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count(); }
static void delay(unsigned us) { std::this_thread::sleep_for(std::chrono::microseconds(us)); }
static uint32_t crc32(const uint8_t* bytes,unsigned size) {
    uint32_t crc=0xffffffff;while(size--){crc^=*bytes++;for(unsigned i=0;i<8;++i)crc=(crc>>1)^(0xedb88320u&uint32_t(-int(crc&1)));}return ~crc;
}
Hardware::Hardware() {
    fd=open("/dev/vision-accel",O_RDWR|O_CLOEXEC);
    if(fd<0) throw std::runtime_error("Cannot open /dev/vision-accel");
    vision_dma_info info{};
    if(ioctl(fd,VISION_DMA_INFO,&info) || info.bytes<VISION_BUFFER_BYTES || info.address+info.bytes>0x100000000ULL){close(fd);fd=-1;throw std::runtime_error("Invalid DMA allocation");}
    bus=uint32_t(info.address);
    auto map=[&](unsigned offset,unsigned size) {return mmap(nullptr,size,PROT_READ|PROT_WRITE,MAP_SHARED,fd,offset);};
    buffer=static_cast<uint8_t*>(map(0,VISION_BUFFER_BYTES));
    gpio=static_cast<volatile uint32_t*>(map(VISION_MAP_GPIO,4096));
    dma=static_cast<volatile uint32_t*>(map(VISION_MAP_CAPTURE,4096));
    conv=static_cast<volatile uint32_t*>(map(VISION_MAP_CONV,4096));
    if(buffer==MAP_FAILED || gpio==MAP_FAILED || dma==MAP_FAILED || conv==MAP_FAILED) {
        if(buffer!=MAP_FAILED)munmap(buffer,VISION_BUFFER_BYTES);
        if(gpio!=MAP_FAILED)munmap(const_cast<uint32_t*>(gpio),4096);
        if(dma!=MAP_FAILED)munmap(const_cast<uint32_t*>(dma),4096);
        if(conv!=MAP_FAILED)munmap(const_cast<uint32_t*>(conv),4096);
        close(fd);fd=-1;throw std::runtime_error("Cannot map accelerator resources");
    }
}
Hardware::~Hardware() {
    {std::lock_guard<std::mutex> lock(exposure_mutex);exposure_stopped=true;}
    exposure_ready.notify_one();
    if(exposure_worker.joinable())exposure_worker.join();
    if(fd<0)return;
    gpio[0]=control&~16u;dma[0x30/4]=4;
    munmap(buffer,VISION_BUFFER_BYTES);munmap(const_cast<uint32_t*>(gpio),4096);munmap(const_cast<uint32_t*>(dma),4096);munmap(const_cast<uint32_t*>(conv),4096);close(fd);
}
void Hardware::pin(unsigned mask,bool high){
    {std::lock_guard<std::mutex> lock(gpio_mutex);control=high?control|mask:control&~mask;gpio[0]=control;}
    if(mask==16){const auto end=clock_ns()+5000;while(clock_ns()<end){}}
    else delay(5);
}
void Hardware::start(){pin(2,true);pin(1,true);pin(2,false);pin(1,false);}
void Hardware::stop(){pin(2,false);pin(1,true);pin(2,true);}
bool Hardware::write_byte(uint8_t v){for(unsigned i=0;i<8;++i){pin(2,v&0x80);pin(1,true);pin(1,false);v<<=1;}pin(2,true);pin(1,true);const bool ack=!(gpio[2]&1);pin(1,false);return ack;}
uint8_t Hardware::read_byte(){uint8_t v=0;pin(2,true);for(unsigned i=0;i<8;++i){pin(1,true);v=(v<<1)|(gpio[2]&1);pin(1,false);}pin(1,true);pin(1,false);return v;}
bool Hardware::write_register(uint16_t address,uint8_t value){start();const bool ok=write_byte(0x78)&&write_byte(address>>8)&&write_byte(address&255)&&write_byte(value);stop();return ok;}
bool Hardware::read_register(uint16_t address,uint8_t& value){start();const bool ok=write_byte(0x78)&&write_byte(address>>8)&&write_byte(address&255);stop();if(!ok)return false;start();const bool read=write_byte(0x79);if(read)value=read_byte();stop();return read;}
void Hardware::initialize_camera() {
    gpio[1]=0;gpio[3]=15;gpio[0]=control;delay(20000);pin(8,false);delay(5000);pin(4,true);delay(20000);
    uint8_t high=0,low=0;
    if(!read_register(0x300a,high)||!read_register(0x300b,low)||high!=0x56||low!=0x40)throw std::runtime_error("OV5640 identification failed");
    if(!write_register(0x3103,0x11)||!write_register(0x3008,0x82))throw std::runtime_error("OV5640 reset failed");
    delay(10000);
    for(const auto& r:camera_registers)if(!write_register(r.address,r.value))throw std::runtime_error("OV5640 configuration failed");
    for(const auto& r:camera_output_registers){uint8_t value=0;if(!write_register(r.address,r.value)||!read_register(r.address,value)||value!=r.value)throw std::runtime_error("OV5640 mode verification failed");}
    delay(300000);
    initialize_exposure();
}
void Hardware::set_exposure_target(unsigned target) {
    const std::pair<uint16_t,uint8_t> values[]={
        {0x3a0f,uint8_t(target+4)},{0x3a10,uint8_t(target-4)},
        {0x3a1b,uint8_t(target+6)},{0x3a1e,uint8_t(target-6)},
        {0x3a11,uint8_t(target*2)},{0x3a1f,uint8_t(target/3)}
    };
    for(const auto& value:values){uint8_t readback=0;
        if(!write_register(value.first,value.second) || !read_register(value.first,readback) || readback!=value.second)
            throw std::runtime_error("Exposure target verification failed");
    }
}
void Hardware::initialize_exposure() {
    auto read=[&](uint16_t address){uint8_t value=0;if(!read_register(address,value))throw std::runtime_error("Exposure register read failed");return unsigned(value);};
    auto& status=exposure_status;
    status.manual=read(0x3503);status.aec_control=read(0x3a00);
    status.vts=(read(0x380e)<<8)|read(0x380f);
    status.maximum=(read(0x3a02)<<8)|read(0x3a03);
    const auto maximum50=(read(0x3a14)<<8)|read(0x3a15);
    status.gain_ceiling=(read(0x3a18)<<8)|read(0x3a19);
    status.gain=((read(0x350a)&3)<<8)|read(0x350b);
    status.exposure_q4=((read(0x3500)&15)<<16)|(read(0x3501)<<8)|read(0x3502);
    if((status.manual&3) || (status.aec_control&4) || status.maximum+4>status.vts || maximum50+4>status.vts)
        throw std::runtime_error("Exposure auto/fixed-frame safety check failed");
    // Sensor coordinates are reversed relative to the displayed 180-degree view.
    // Display weights: 1,1,1,1 / 2,4,4,2 / 4,8,8,4 / 4,6,6,4.
    const uint8_t weights[]={0x64,0x46,0x84,0x48,0x42,0x24,0x11,0x11};
    for(unsigned i=0;i<8;++i){uint8_t actual=0;
        if(!write_register(0x5688+i,weights[i]) || !read_register(0x5688+i,actual) || actual!=weights[i])
            throw std::runtime_error("Exposure metering verification failed");
    }
    set_exposure_target(status.target);
    exposure_worker=std::thread([this]{exposure_loop();});
}
void Hardware::exposure_loop() {
    for(;;){
        ExposureMeter meter;
        {std::unique_lock<std::mutex> lock(exposure_mutex);
         exposure_ready.wait(lock,[this]{return exposure_stopped || exposure_pending;});
         if(exposure_stopped)return;
         meter=exposure_status.corrected;meter.high=std::max(meter.high,exposure_status.raw.high);exposure_pending=false;}
        const auto target=exposure_policy.update(meter,clock_ns());
        {std::lock_guard<std::mutex> lock(exposure_mutex);if(target==exposure_status.target)continue;}
        try{
            // Slow SCCB traffic runs outside the capture/preprocessing thread.
            set_exposure_target(target);
            std::lock_guard<std::mutex> lock(exposure_mutex);exposure_status.target=target;++exposure_status.updates;
        }catch(const std::exception& e){
            std::lock_guard<std::mutex> lock(exposure_mutex);exposure_status.error=e.what();return;
        }
    }
}
CameraExposure Hardware::camera_exposure() {std::lock_guard<std::mutex> lock(exposure_mutex);return exposure_status;}
void Hardware::set_shading(std::vector<uint16_t> gains) {shading=std::move(gains);}
std::shared_ptr<const Hardware::Model> Hardware::validate_model(std::vector<uint8_t> file,const std::string& version,const std::string& expected_payload,const std::string& expected_file) {
    if(file.size()!=128+weight_bytes+metadata_words*4 || sha256(file.data(),file.size())!=expected_file)throw std::runtime_error("Model file checksum mismatch");
    auto word=[&](unsigned offset){uint32_t value;std::memcpy(&value,file.data()+offset,4);return value;};
    if(word(0)!=0x314e4e43 || word(4)!=1 || word(8)!=weight_bytes || word(12)!=metadata_words*4 || word(16)||word(20)||word(124)||word(120)!=crc32(file.data(),120))throw std::runtime_error("Invalid model header");
    if(version.empty() || version.size()>63 || std::memcmp(file.data()+24,version.c_str(),version.size()+1))throw std::runtime_error("Model version mismatch");
    if(sha256(file.data()+128,file.size()-128)!=expected_payload)throw std::runtime_error("Model payload checksum mismatch");
    auto graph=reinterpret_cast<const int32_t*>(file.data()+128+weight_bytes);
    if(graph[4]!=1 && graph[4]!=3)throw std::runtime_error("Unsupported input channels");
    for(unsigned i=0;i<33;++i)for(unsigned j=0;j<10;++j)if(!(i==0 && j==4) && graph[i*10+j]!=model_commands[i][j])throw std::runtime_error("Model graph mismatch");
    const unsigned channels=graph[4];
    auto model=std::shared_ptr<Model>(new Model(std::move(file)));
    model->channels=channels;model->level=expected_file==level_model_sha256;
    return model;
}
void Hardware::load_model(const Model& model) {
    if(!(conv[0]&4))throw std::runtime_error("Accelerator is busy; reset the PL before loading a model");
    const auto& file=model.bytes;const auto graph=reinterpret_cast<const int32_t*>(file.data()+128+weight_bytes);
    channels=model.channels;
    level_enabled=model.level;
    captured_level=LevelFrame{};
    have_frame=false;current=0;captured_ns=0;
    std::memcpy(commands,graph,sizeof(commands));
    gray.assign(3*224*224,0);
    out0_raw.assign(1847,0);out1_raw.assign(7390,0);
    std::memcpy(buffer,file.data()+128,weight_bytes+metadata_words*4);
    std::atomic_thread_fence(std::memory_order_seq_cst);
}
void Hardware::start_capture(unsigned index) {
    pin(16,false);dma[0x30/4]=4;const auto deadline=clock_ns()+1000000000ULL;
    while(dma[0x30/4]&4){if(clock_ns()>deadline)throw std::runtime_error("Capture DMA reset timeout");delay(50);}
    dma[0x34/4]=0x7000;dma[0x30/4]=1;dma[0x48/4]=bus+pixels_offset+index*camera_bytes;dma[0x58/4]=camera_bytes;
    std::atomic_thread_fence(std::memory_order_seq_cst);pin(16,true);
}
void Hardware::wait_capture() {
    const auto deadline=clock_ns()+2000000000ULL;
    for(;;){const auto status=dma[0x34/4];if((status&0x770)||(gpio[2]&2)){pin(16,false);dma[0x30/4]=4;throw std::runtime_error("Camera/DMA capture error");}if(status&0x1000)break;if(clock_ns()>deadline){pin(16,false);dma[0x30/4]=4;throw std::runtime_error("Capture timeout");}delay(50);}
    pin(16,false);if(dma[0x58/4]!=camera_bytes)throw std::runtime_error("Incomplete frame");
}
Frame Hardware::capture() {
    if(!channels)throw std::runtime_error("No validated model loaded");
    if(!have_frame){current=0;start_capture(current);captured_ns=prepare_capture(current);have_frame=true;}
    const auto prepare_begin=clock_ns();
    Frame frame;frame.id=++sequence;frame.monotonic_ns=captured_ns;
    frame.pixels.swap(captured_pixels);
    frame.level=std::move(captured_level);
    auto features=reinterpret_cast<int8_t*>(buffer+feature_offset);
    for(unsigned c=0;c<channels;++c)for(unsigned y=0;y<224;++y)std::memcpy(features+c*224*256+y*256,gray.data()+c*224*224+y*224,224);
    prepare_ns.store(clock_ns()-prepare_begin);
    const unsigned next=current^1;
    const auto forward_begin=clock_ns();
    // The worker owns camera completion and next-frame preprocessing until get().
    // Keep that work outside the loop that launches the 33 accelerator layers.
    auto preparation=std::async(std::launch::async,[this,next]{
        cpu_set_t cpu;CPU_ZERO(&cpu);CPU_SET(0,&cpu);
        if(sched_setaffinity(0,sizeof(cpu),&cpu))throw std::runtime_error("Cannot assign preprocessing CPU");
        return prepare_capture(next);
    });
    const auto inference_deadline=clock_ns()+2000000000ULL;
    const auto conv_begin=clock_ns();
    for(unsigned layer=0;layer<33;++layer) {
        const int32_t* c=commands+layer*10;
        for(unsigned reg:{0x10u,0x18u,0x20u,0x28u})conv[reg/4]=bus+feature_offset+c[0];
        for(unsigned reg:{0x30u,0x38u,0x40u,0x48u})conv[reg/4]=bus+c[2];
        conv[0x50/4]=bus+metadata_offset+c[3]*4;
        for(unsigned reg:{0x58u,0x60u,0x68u,0x70u})conv[reg/4]=bus+feature_offset+c[1];
        for(unsigned j=4;j<10;++j)conv[(0x78+(j-4)*8)/4]=c[j];
        std::atomic_thread_fence(std::memory_order_seq_cst);conv[0]=1;
        while(!(conv[0]&2)){
            if(clock_ns()>inference_deadline)throw std::runtime_error("PL inference timeout");
            // Keep layer hand-off immediate; inference has its own CPU.
        }
    }
    conv_ns.store(clock_ns()-conv_begin);
    const auto next_captured_ns=preparation.get();
    forward_ns.store(clock_ns()-forward_begin);
    const auto post_begin=clock_ns();
    std::atomic_thread_fence(std::memory_order_seq_cst);
    const auto extract_begin=clock_ns();
    std::memcpy(out0_raw.data(),features+out0_offset,out0_raw.size());
    std::memcpy(out1_raw.data(),features+out1_offset,out1_raw.size());
    frame.out0.resize(1617);frame.out1.resize(6468);
    for(unsigned i=0;i<1617;++i)frame.out0[i]=out0_raw[(i/7)*8+i%7];
    for(unsigned i=0;i<6468;++i)frame.out1[i]=out1_raw[(i/14)*16+i%14];
    extract_ns.store(clock_ns()-extract_begin);
    current=next;captured_ns=next_captured_ns;
    post_ns.store(clock_ns()-post_begin);
    return frame;
}
uint64_t Hardware::prepare_capture(unsigned index) {
    wait_capture();
    const auto captured=clock_ns();
    std::atomic_thread_fence(std::memory_order_seq_cst);
    captured_pixels.resize(416*416);
    std::memcpy(captured_pixels.data(),buffer+pixels_offset+index*camera_bytes,camera_bytes);
    const bool meter_due=captured>=next_metering_ns;
    ExposureMeter raw_meter;
    if(meter_due)raw_meter=exposure_meter(captured_pixels.data(),true);
    if(!shading.empty()){
        // Gains remain Q8 with the same rounding and saturation as the scalar path.
        for(unsigned i=0;i<416u*416u;i+=8){
            const auto p=vld1q_u16(captured_pixels.data()+i);
            const auto r5=vshrq_n_u16(p,11),g6=vandq_u16(vshrq_n_u16(p,5),vdupq_n_u16(63)),b5=vandq_u16(p,vdupq_n_u16(31));
            const auto gain=vld3q_u16(shading.data()+i*3);
            auto corrected=[](uint16x8_t c,uint16x8_t gain){
                const auto lo=vaddq_u32(vmull_u16(vget_low_u16(c),vget_low_u16(gain)),vdupq_n_u32(128));
                const auto hi=vaddq_u32(vmull_u16(vget_high_u16(c),vget_high_u16(gain)),vdupq_n_u32(128));
                return vminq_u16(vcombine_u16(vshrn_n_u32(lo,8),vshrn_n_u32(hi,8)),vdupq_n_u16(255));
            };
            const auto r=corrected(vorrq_u16(vshlq_n_u16(r5,3),vshrq_n_u16(r5,2)),gain.val[0]);
            const auto g=corrected(vorrq_u16(vshlq_n_u16(g6,2),vshrq_n_u16(g6,4)),gain.val[1]);
            const auto b=corrected(vorrq_u16(vshlq_n_u16(b5,3),vshrq_n_u16(b5,2)),gain.val[2]);
            vst1q_u16(captured_pixels.data()+i,vorrq_u16(vorrq_u16(vshlq_n_u16(vshrq_n_u16(r,3),11),vshlq_n_u16(vshrq_n_u16(g,2),5)),vshrq_n_u16(b,3)));
        }
    }
    // Rotate the corrected RGB565 frame by 180 degrees before both inference
    // preprocessing and preview consume it. Shading remains in sensor coordinates.
    std::reverse(captured_pixels.begin(),captured_pixels.end());
    // The previous pixels are cached now; rearm the other DMA buffer immediately,
    // as in the bare-metal pipeline, before preprocessing or the next inference.
    start_capture(index^1);
    if(meter_due){
        const auto corrected=shading.empty()?raw_meter:exposure_meter(captured_pixels.data(),false);
        {std::lock_guard<std::mutex> lock(exposure_mutex);exposure_status.raw=raw_meter;exposure_status.corrected=corrected;++exposure_status.samples;exposure_pending=true;}
        next_metering_ns=captured+500000000ULL;exposure_ready.notify_one();
    }
    if(level_enabled){
        captured_level=prepare_level_rgb565(captured_pixels.data());
        for(unsigned i=0;i<224*224;++i)gray[i]=int8_t((unsigned(captured_level.gray[i])*127+127)/255);
    }else model_input_rows(captured_pixels.data(),gray.data(),0,640,channels);
    return captured;
}
}
