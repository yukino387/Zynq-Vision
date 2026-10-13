#include "../../hardware/hls/src/top.h"
#include "../../hardware/hls/src/layout.h"
#include "../../hardware/hls/src/packed_multiply.h"
#include "build/model.h"
#include <vector>
#include <fstream>
#include <iostream>
#include <string>
#include <stdexcept>

static const std::string directory="C:/00_workplace/fpga/cnn_accelerator/temporary/int8_rebuild_test/build/";
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
    auto features=read<data_t>("features.bin",feature_bytes);
    features.resize(feature_bytes+64,data_t(0x55));
    auto weights=read<data_t>("weights.bin",weight_bytes);
    auto metadata=read<int32_t>("metadata.bin",metadata_words);
    for(unsigned layer=0;layer<command_count;++layer) {
        const auto* c=metadata.data()+10*layer;
        const auto* input=reinterpret_cast<const uint64_t*>(features.data()+c[0]);
        const auto* weight=reinterpret_cast<const uint64_t*>(weights.data()+c[2]);
        auto* output=reinterpret_cast<uint64_t*>(features.data()+c[1]);
        conv(input,input,input,input,weight,weight,weight,weight,metadata.data()+c[3],
             output,output,output,output,c[4],c[5],c[6],c[7],c[8],c[9]);
    }
    for (const auto& check: checks) {
        auto expected=read<data_t>("../../int8_model_test/build/golden/"+std::string(check.name)+".bin",check.channels*check.size*check.size);
        for (unsigned i=0;i<check.channels*check.size*check.size;++i) if (features[check.offset+(i/check.size)*row_pitch(check.size)+i%check.size]!=expected[i]) {
            std::cerr<<"FAIL "<<check.name<<" index="<<i<<" got="<<int(features[check.offset+(i/check.size)*row_pitch(check.size)+i%check.size])
                     <<" expected="<<int(expected[i])<<std::endl;
            return 1;
        }
        for(unsigned row=0;row<check.channels*check.size;++row)
            for(unsigned col=check.size;col<row_pitch(check.size);++col)
                if(features[check.offset+row*row_pitch(check.size)+col]!=0)
                    throw std::runtime_error(std::string(check.name)+" padding modified");
        std::cout<<"PASS "<<check.name<<" elements="<<check.channels*check.size*check.size<<std::endl;
    }
    for(unsigned i=feature_bytes;i<features.size();++i)
        if(features[i]!=data_t(0x55)) throw std::runtime_error("Feature guard modified");
    std::cout<<"PASS PS scheduled aligned W8A8 network against all reference stages"<<std::endl;
    return 0;
}
