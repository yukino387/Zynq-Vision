#include "hardware.h"
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <stdexcept>
namespace terminal {
Hardware::Hardware(){}
Hardware::~Hardware(){}
void Hardware::initialize_camera(){}
void Hardware::load_model(const std::vector<uint8_t>&,const std::string&,const std::string&,const std::string&){
    if(std::filesystem::exists(std::filesystem::path(std::getenv("VISION_ENGINE_TEST_ROOT"))/"fail-model"))throw std::runtime_error("Fixture model load failure");
}
Frame Hardware::capture(){
    static unsigned previous=0;static uint64_t timestamp=0;
    unsigned generation=0;std::ifstream file(std::filesystem::path(std::getenv("VISION_ENGINE_TEST_ROOT"))/"frame");file>>generation;
    if(generation!=previous){previous=generation;timestamp=std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();}
    Frame frame;frame.id=generation;frame.monotonic_ns=timestamp;frame.pixels.resize(416*416);
    for(unsigned y=0;y<416;++y)for(unsigned x=0;x<416;++x)frame.pixels[y*416+x]=((x/4+y/4)%2)?0x8c71:0x6b4d;
    frame.out0.assign(1617,-128);frame.out1.assign(6468,-128);return frame;
}
}
