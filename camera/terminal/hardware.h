#pragma once
#include <cstdint>
#include <string>
#include <vector>
namespace terminal {
struct Frame {
    uint32_t id=0;
    uint64_t monotonic_ns=0;
    std::vector<uint16_t> pixels;
    std::vector<int8_t> out0,out1;
};
class Hardware {
    int fd=-1;
    uint8_t* buffer=nullptr;
    volatile uint32_t *gpio=nullptr,*dma=nullptr,*conv=nullptr;
    uint32_t bus=0,control=3,sequence=0;
    unsigned channels=0;
    void pin(unsigned,bool);
    void start();void stop();
    bool write_byte(uint8_t);
    uint8_t read_byte();
    bool write_register(uint16_t,uint8_t);
    bool read_register(uint16_t,uint8_t&);
public:
    Hardware();~Hardware();
    Hardware(const Hardware&)=delete;
    Hardware& operator=(const Hardware&)=delete;
    void initialize_camera();
    void load_model(const std::vector<uint8_t>&,const std::string&,const std::string&,const std::string&);
    Frame capture();
};
}
