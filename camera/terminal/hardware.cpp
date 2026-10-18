#include "hardware.h"
#include "core.h"
#include "linux/vision_uapi.h"
#include "model_graph.h"
#include "../int8/model.h"
#include "../int8/gray.h"
#include "../../hardware/camera/ov5640_registers.h"
#include "../../hardware/camera/ov5640_mode.h"
#include <atomic>
#include <chrono>
#include <cstring>
#include <stdexcept>
#include <thread>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>

namespace terminal {
static constexpr unsigned metadata_offset=weight_bytes,feature_offset=(weight_bytes+metadata_words*4+63)&~63u;
static constexpr unsigned pixels_offset=(feature_offset+feature_bytes+63)&~63u;
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
    if(fd<0)return;
    gpio[0]=control&~16u;dma[0x30/4]=4;
    munmap(buffer,VISION_BUFFER_BYTES);munmap(const_cast<uint32_t*>(gpio),4096);munmap(const_cast<uint32_t*>(dma),4096);munmap(const_cast<uint32_t*>(conv),4096);close(fd);
}
void Hardware::pin(unsigned mask,bool high){control=high?control|mask:control&~mask;gpio[0]=control;delay(5);}
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
}
void Hardware::load_model(const std::vector<uint8_t>& file,const std::string& version,const std::string& expected_payload,const std::string& expected_file) {
    if(!(conv[0]&4))throw std::runtime_error("Accelerator is busy; reset the PL before loading a model");
    if(file.size()!=128+weight_bytes+metadata_words*4 || sha256(file.data(),file.size())!=expected_file)throw std::runtime_error("Model file checksum mismatch");
    auto word=[&](unsigned offset){uint32_t value;std::memcpy(&value,file.data()+offset,4);return value;};
    if(word(0)!=0x314e4e43 || word(4)!=1 || word(8)!=weight_bytes || word(12)!=metadata_words*4 || word(16)||word(20)||word(124)||word(120)!=crc32(file.data(),120))throw std::runtime_error("Invalid model header");
    if(version.empty() || version.size()>63 || std::memcmp(file.data()+24,version.c_str(),version.size()+1))throw std::runtime_error("Model version mismatch");
    if(sha256(file.data()+128,file.size()-128)!=expected_payload)throw std::runtime_error("Model payload checksum mismatch");
    auto graph=reinterpret_cast<const int32_t*>(file.data()+128+weight_bytes);
    if(graph[4]!=1 && graph[4]!=3)throw std::runtime_error("Unsupported input channels");
    for(unsigned i=0;i<33;++i)for(unsigned j=0;j<10;++j)if(!(i==0 && j==4) && graph[i*10+j]!=model_commands[i][j])throw std::runtime_error("Model graph mismatch");
    channels=graph[4];
    std::memcpy(buffer,file.data()+128,weight_bytes+metadata_words*4);
    std::atomic_thread_fence(std::memory_order_seq_cst);
}
Frame Hardware::capture() {
    if(!channels)throw std::runtime_error("No validated model loaded");
    auto pixels=reinterpret_cast<uint16_t*>(buffer+pixels_offset);
    pin(16,false);dma[0x30/4]=4;auto deadline=clock_ns()+1000000000ULL;
    while(dma[0x30/4]&4){if(clock_ns()>deadline)throw std::runtime_error("Capture DMA reset timeout");delay(50);}
    dma[0x34/4]=0x7000;dma[0x30/4]=1;dma[0x48/4]=bus+pixels_offset;dma[0x58/4]=416*416*2;
    std::atomic_thread_fence(std::memory_order_seq_cst);pin(16,true);deadline=clock_ns()+2000000000ULL;
    for(;;){const auto status=dma[0x34/4];if((status&0x770)||(gpio[2]&2)){pin(16,false);dma[0x30/4]=4;throw std::runtime_error("Camera/DMA capture error");}if(status&0x1000)break;if(clock_ns()>deadline){pin(16,false);dma[0x30/4]=4;throw std::runtime_error("Capture timeout");}delay(50);}
    pin(16,false);if(dma[0x58/4]!=416*416*2)throw std::runtime_error("Incomplete frame");
    const auto acquired=clock_ns();
    std::atomic_thread_fence(std::memory_order_seq_cst);
    std::vector<int8_t> input(3*224*224);
    model_input_rows(pixels,input.data(),0,640,channels);
    auto features=reinterpret_cast<int8_t*>(buffer+feature_offset);
    for(unsigned c=0;c<channels;++c)for(unsigned y=0;y<224;++y)std::memcpy(features+c*224*256+y*256,input.data()+c*224*224+y*224,224);
    const auto metadata=reinterpret_cast<int32_t*>(buffer+metadata_offset);
    const auto inference_deadline=clock_ns()+2000000000ULL;
    for(unsigned layer=0;layer<33;++layer) {
        const int32_t* c=metadata+layer*10;
        for(unsigned reg:{0x10u,0x18u,0x20u,0x28u})conv[reg/4]=bus+feature_offset+c[0];
        for(unsigned reg:{0x30u,0x38u,0x40u,0x48u})conv[reg/4]=bus+c[2];
        conv[0x50/4]=bus+metadata_offset+c[3]*4;
        for(unsigned reg:{0x58u,0x60u,0x68u,0x70u})conv[reg/4]=bus+feature_offset+c[1];
        for(unsigned j=4;j<10;++j)conv[(0x78+(j-4)*8)/4]=c[j];
        std::atomic_thread_fence(std::memory_order_seq_cst);conv[0]=1;
        while(!(conv[0]&2)){if(clock_ns()>inference_deadline)throw std::runtime_error("PL inference timeout");delay(50);}
    }
    std::atomic_thread_fence(std::memory_order_seq_cst);
    Frame frame;frame.id=++sequence;frame.monotonic_ns=acquired;frame.pixels.assign(pixels,pixels+416*416);frame.out0.resize(1617);frame.out1.resize(6468);
    for(unsigned i=0;i<1617;++i)frame.out0[i]=features[out0_offset+(i/7)*8+i%7];
    for(unsigned i=0;i<6468;++i)frame.out1[i]=features[out1_offset+(i/14)*16+i%14];
    return frame;
}
}
