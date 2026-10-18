#include "top.h"
#include <vector>
#include <fstream>
#include <iostream>
#include <cstring>
#include <string>

static std::vector<char> read(const std::string& path) {
    std::ifstream stream(path,std::ios::binary);
    if(!stream)throw std::runtime_error(path);
    return {std::istreambuf_iterator<char>(stream),std::istreambuf_iterator<char>()};
}
int main(int argc,char** argv) {
    if(argc!=2)return 2;
    const std::string dir=argv[1];
    auto w=read(dir+"/weights.bin"),m=read(dir+"/metadata.bin"),input=read(dir+"/verify-input.bin");
    auto expected0=read(dir+"/expected-out0.bin"),expected1=read(dir+"/expected-out1.bin");
    std::vector<uint64_t> features((3012640+7)/8,0);
    auto bytes=reinterpret_cast<char*>(features.data());
    auto metadata=reinterpret_cast<int32_t*>(m.data());
    for(unsigned c=0;c<unsigned(metadata[4]);++c)for(unsigned y=0;y<224;++y)
        std::memcpy(bytes+c*224*256+y*256,input.data()+c*224*224+y*224,224);
    for(unsigned layer=0;layer<33;++layer) {
        const int32_t* c=metadata+layer*10;
        const uint64_t* source=reinterpret_cast<uint64_t*>(bytes+c[0]);
        uint64_t* dest=reinterpret_cast<uint64_t*>(bytes+c[1]);
        const uint64_t* weight=reinterpret_cast<uint64_t*>(w.data()+c[2]);
        conv(source,source,source,source,weight,weight,weight,weight,metadata+c[3],dest,dest,dest,dest,c[4],c[5],c[6],c[7],c[8],c[9]);
    }
    for(unsigned h=0;h<2;++h) {
        unsigned size=h?14:7,pitch=h?16:8,offset=h?3005248:2910208;
        const auto& expected=h?expected1:expected0;
        for(unsigned i=0;i<expected.size();++i)if(bytes[offset+(i/size)*pitch+i%size]!=expected[i]) {
            std::cerr<<"FAIL head="<<h<<" index="<<i<<" actual="<<int(int8_t(bytes[offset+(i/size)*pitch+i%size]))<<" expected="<<int(int8_t(expected[i]))<<"\n";
            return 1;
        }
    }
    std::cout<<"PASS: all 33 HLS commands match INT8 reference, input channels="<<metadata[4]<<"\n";
}
