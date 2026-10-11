#include "yolo4_tiny.h"
#include "xil_cache.h"
#include <cassert>
#include <cstring>
#include <iostream>
#include <limits>
#include <vector>
struct Region { INTPTR address; std::vector<unsigned char> bytes; };
static std::vector<Region> regions;
static unsigned flushes, repeated, calls;
static bool running;
void Xil_DCacheFlushRange(INTPTR address, std::size_t bytes) {
    for (Region& region : regions) if (region.address == address) {
        if (running) { ++repeated; return; }
        region.bytes.assign(reinterpret_cast<unsigned char*>(address), reinterpret_cast<unsigned char*>(address)+bytes);
        ++flushes;
        return;
    }
    if (!running) {
        regions.push_back({address, std::vector<unsigned char>(reinterpret_cast<unsigned char*>(address), reinterpret_cast<unsigned char*>(address)+bytes)});
        ++flushes;
    }
}
void Xil_DCacheInvalidateRange(INTPTR, std::size_t) {}
static void visible(data_t* data) {
    for (const Region& region : regions) if (region.address == reinterpret_cast<INTPTR>(data)) {
        assert(!std::memcmp(data, region.bytes.data(), region.bytes.size()));
        return;
    }
    assert(false);
}
void conv_init() {}
void conv_leakyrelu(int, int co, int p, int s, int k, int h, int w,
                   data_t*, data_t* weight, data_t* bias, data_t* output, int) {
    visible(weight); visible(bias); ++calls;
    std::memset(output, 0, co*((h+2*p-k)/s+1)*((w+2*p-k)/s+1)*sizeof(data_t));
}
void sampling(data_t*, data_t* out, int ch, int size, int mode) {
    const int oh=mode ? size/2 : size*2;
    std::memset(out, 0, ch*oh*oh*sizeof(data_t));
}
static bool reader(const char*, float* data, std::size_t count, void* context) {
    for (std::size_t i=0; i<count; ++i) data[i]=*static_cast<float*>(context);
    return true;
}
int main() {
    Yolo4_Tiny net;
    float value=0.125f;
    assert(net.load_weight("weights", reader, &value));
    assert(regions.size()==42 && flushes==42);
    std::size_t bytes=0;
    for (const Region& region : regions) bytes+=region.bytes.size();
    std::vector<data_t> input(CSPDarkNet::INPUT_COUNT), out0(Yolo4_Tiny::OUT0_COUNT), out1(Yolo4_Tiny::OUT1_COUNT);
    running=true;
    net.forward(input.data(), out0.data(), out1.data());
    net.forward(input.data(), out0.data(), out1.data());
    assert(calls==42 && repeated==0);
    running=false; value=0.25f;
    assert(net.load_weight("weights", reader, &value));
    assert(regions.size()==42 && flushes==84);
    running=true; net.forward(input.data(), out0.data(), out1.data());
    assert(calls==63 && repeated==0);
    running=false; value=std::numeric_limits<float>::quiet_NaN();
    assert(!net.load_weight("weights", reader, &value));
    assert(flushes==84);
    running=true; net.forward(input.data(), out0.data(), out1.data());
    assert(calls==84 && repeated==0);
    std::cout << "PASS: 42 buffers flushed per load, 4 forwards including rejected reload, no repeated weight flush; saved " << bytes << " bytes per frame\n";
}
