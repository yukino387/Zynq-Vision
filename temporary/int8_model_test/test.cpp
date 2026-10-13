#include "src/top.h"
#include "src/write_bytes.h"
#include "src/packed_multiply.h"
#include "build/model.h"
#include <vector>
#include <fstream>
#include <iostream>
#include <string>
#include <stdexcept>

static const std::string directory="C:/00_workplace/fpga/cnn_accelerator/temporary/int8_model_test/build/";
template<class T> static std::vector<T> read(const std::string& name, unsigned count) {
    std::vector<T> values(count);
    std::ifstream file(directory+name,std::ios::binary);
    if (!file.read(reinterpret_cast<char*>(values.data()),count*sizeof(T))) throw std::runtime_error(name);
    return values;
}

int main() {
    for(int x=-128;x<128;++x) for(int a=-128;a<128;++a) for(int b=-128;b<128;++b) {
        int16_t first,second;
        multiply_pair(x,a,b,first,second);
        if(first!=x*a || second!=x*b) throw std::runtime_error("Packed multiplier failed");
    }
    std::cout<<"PASS packed multiplication: all 16777216 signed INT8 triples"<<std::endl;
    data_t values[512];
    uint64_t packed[80];
    for(unsigned i=0;i<512;++i) values[i]=data_t(i*37+19);
    for(unsigned start=0;start<16;++start) for(unsigned count=0;count<=512;++count) {
        for(auto& word:packed) word=0x5555555555555555ull;
        write_bytes<0,512>(packed,start,values,count);
        const auto* bytes=reinterpret_cast<const data_t*>(packed);
        for(unsigned i=0;i<sizeof(packed);++i)
            if(bytes[i]!=(i>=start && i<start+count ? values[i-start] : data_t(0x55)))
                throw std::runtime_error("Packed write alignment/guard failed");
    }
    std::cout<<"PASS packed writes: every offset/length and adjacent guards"<<std::endl;
    auto features=read<data_t>("features.bin",feature_bytes);
    features.resize(feature_bytes+64,data_t(0x55));
    auto weights=read<data_t>("weights.bin",weight_bytes);
    auto metadata=read<int32_t>("metadata.bin",metadata_words);
    const auto* input=reinterpret_cast<const uint64_t*>(features.data());
    const auto* weight=reinterpret_cast<const uint64_t*>(weights.data());
    conv(input,input,input,input,weight,weight,weight,weight,metadata.data(),
         reinterpret_cast<uint64_t*>(features.data()),reinterpret_cast<uint64_t*>(features.data()),
         reinterpret_cast<uint64_t*>(features.data()),reinterpret_cast<uint64_t*>(features.data()),
         command_count,0,0,0,4,0);
    for (const auto& check: checks) {
        auto expected=read<data_t>("golden/"+std::string(check.name)+".bin",check.count);
        for (unsigned i=0;i<check.count;++i) if (features[check.offset+i]!=expected[i]) {
            std::cerr<<"FAIL "<<check.name<<" index="<<i<<" got="<<int(features[check.offset+i])
                     <<" expected="<<int(expected[i])<<std::endl;
            return 1;
        }
        std::cout<<"PASS "<<check.name<<" elements="<<check.count<<std::endl;
    }
    for(unsigned i=feature_bytes;i<features.size();++i)
        if(features[i]!=data_t(0x55)) throw std::runtime_error("Feature guard modified");
    std::cout<<"PASS full W8A8 PL command program against all reference stages"<<std::endl;
    return 0;
}
