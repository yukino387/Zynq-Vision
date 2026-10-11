#include "yolo4_tiny.h"
#include "xil_cache.h"
#include <cassert>
#include <cstring>
#include <iostream>
#include <limits>
#include <vector>
struct Region { INTPTR address; std::vector<unsigned char> bytes; };
static std::vector<Region> regions;
static std::vector<Region> features;
static std::vector<std::pair<INTPTR, std::size_t>> prepared;
static std::size_t feature_flush_bytes;
static unsigned flushes, repeated, calls;
static bool running;
static void publish_feature(INTPTR address, std::size_t bytes) {
    bool exists=false;
    for (Region& region : features) {
        const INTPTR first=address>region.address ? address : region.address;
        const INTPTR end=address+bytes<region.address+region.bytes.size() ? address+bytes : region.address+region.bytes.size();
        if (first<end) std::memcpy(region.bytes.data()+first-region.address, reinterpret_cast<void*>(first), end-first);
        if (region.address==address && region.bytes.size()==bytes) exists=true;
    }
    if (!exists) features.push_back({address, std::vector<unsigned char>(reinterpret_cast<unsigned char*>(address), reinterpret_cast<unsigned char*>(address)+bytes)});
}
static void visible_feature(data_t* data, std::size_t bytes) {
    INTPTR cursor=reinterpret_cast<INTPTR>(data), end=cursor+bytes;
    while (cursor<end) {
        bool found=false;
        for (const Region& region : features) if (cursor>=region.address && cursor<region.address+region.bytes.size()) {
            const INTPTR stop=end<region.address+region.bytes.size() ? end : region.address+region.bytes.size();
            assert(!std::memcmp(reinterpret_cast<void*>(cursor), region.bytes.data()+cursor-region.address, stop-cursor));
            cursor=stop; found=true; break;
        }
        assert(found);
    }
}
static void prepared_output(data_t* data, std::size_t bytes) {
    INTPTR cursor=reinterpret_cast<INTPTR>(data), end=cursor+bytes;
    while (cursor<end) {
        bool found=false;
        for (const auto& region : prepared) if (cursor>=region.first && cursor<region.first+region.second) {
            cursor=end<region.first+region.second ? end : region.first+region.second;
            found=true; break;
        }
        assert(found);
    }
}
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
    } else {
        feature_flush_bytes+=bytes;
        prepared.push_back({address, bytes});
        publish_feature(address, bytes);
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
void conv_leakyrelu(int ci, int co, int p, int s, int k, int h, int w,
                   data_t* input, data_t* weight, data_t* bias, data_t* output, int) {
    visible(weight); visible(bias); ++calls;
    visible_feature(input, ci*h*w*sizeof(data_t));
    const std::size_t bytes=co*((h+2*p-k)/s+1)*((w+2*p-k)/s+1)*sizeof(data_t);
    prepared_output(output, bytes);
    for (std::size_t i=0; i<bytes/sizeof(data_t); ++i)
        output[i]=static_cast<data_t>(calls*97+i%23);
    publish_feature(reinterpret_cast<INTPTR>(output), bytes);
}
void sampling(data_t* input, data_t* out, int ch, int size, int mode) {
    visible_feature(input, ch*size*size*sizeof(data_t));
    const int oh=mode ? size/2 : size*2;
    prepared_output(out, ch*oh*oh*sizeof(data_t));
    for (int c=0; c<ch; ++c) for (int y=0; y<oh; ++y) for (int x=0; x<oh; ++x)
        out[c*oh*oh+y*oh+x]=input[c*size*size+(mode ? y*2 : y/2)*size+(mode ? x*2 : x/2)];
    publish_feature(reinterpret_cast<INTPTR>(out), ch*oh*oh*sizeof(data_t));
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
    input[0]=1;
    prepared.clear();
    net.forward(input.data(), out0.data(), out1.data());
    input[0]=2;
    prepared.clear();
    net.forward(input.data(), out0.data(), out1.data());
    assert(calls==42 && repeated==0);
    running=false; value=0.25f;
    assert(net.load_weight("weights", reader, &value));
    assert(regions.size()==42 && flushes==84);
    running=true; prepared.clear(); net.forward(input.data(), out0.data(), out1.data());
    assert(calls==63 && repeated==0);
    running=false; value=std::numeric_limits<float>::quiet_NaN();
    assert(!net.load_weight("weights", reader, &value));
    assert(flushes==84);
    running=true; prepared.clear(); net.forward(input.data(), out0.data(), out1.data());
    assert(calls==84 && repeated==0);
    std::cout << "Feature flush bytes per frame: " << feature_flush_bytes/4 << '\n';
    std::cout << "PASS: 42 buffers flushed per load, 4 forwards including rejected reload, no repeated weight flush; saved " << bytes << " bytes per frame\n";
}
