#include "src/top.h"
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
    auto features=read<data_t>("features.bin",feature_bytes);
    auto weights=read<data_t>("weights.bin",weight_bytes);
    auto metadata=read<int32_t>("metadata.bin",metadata_words);
    conv(features.data(),features.data(),features.data(),features.data(),
         weights.data(),weights.data(),weights.data(),weights.data(),metadata.data(),
         features.data(),features.data(),features.data(),features.data(),
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
    std::cout<<"PASS full W8A8 PL command program against all reference stages"<<std::endl;
    return 0;
}
