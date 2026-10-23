#pragma once
#include <atomic>
#include <cstdint>
#include <string>
#include <vector>
#include "level_compat.h"
namespace terminal {
struct Frame {
    uint32_t id=0;
    uint64_t monotonic_ns=0;
    std::vector<uint16_t> pixels;
    std::vector<int8_t> out0,out1;
    LevelFrame level;
};
class Hardware {
    int fd=-1;
    uint8_t* buffer=nullptr;
    volatile uint32_t *gpio=nullptr,*dma=nullptr,*conv=nullptr;
    uint32_t bus=0,control=3,sequence=0;
    unsigned channels=0;
    unsigned current=0;
    bool have_frame=false;
    bool level_enabled=false;
    LevelFrame captured_level;
    uint64_t captured_ns=0;
    int32_t commands[330]{};
    std::vector<uint16_t> captured_pixels;
    std::vector<uint16_t> shading;
    std::vector<int8_t> gray,out0_raw,out1_raw;
    void pin(unsigned,bool);
    void start();void stop();
    void start_capture(unsigned);
    void wait_capture();
    uint64_t prepare_capture(unsigned);
    bool write_byte(uint8_t);
    uint8_t read_byte();
    bool write_register(uint16_t,uint8_t);
    bool read_register(uint16_t,uint8_t&);
public:
    std::atomic<uint64_t> prepare_ns{0},conv_ns{0},forward_ns{0},post_ns{0},extract_ns{0};
    Hardware();~Hardware();
    Hardware(const Hardware&)=delete;
    Hardware& operator=(const Hardware&)=delete;
    void initialize_camera();
    void set_shading(std::vector<uint16_t>);
    void load_model(const std::vector<uint8_t>&,const std::string&,const std::string&,const std::string&);
    Frame capture();
};
}
