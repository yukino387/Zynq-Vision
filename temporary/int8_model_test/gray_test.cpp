#include "gray.h"
#include <fstream>
#include <iostream>

int main() {
    const char* root="C:/00_workplace/fpga/cnn_accelerator/temporary/int8_model_test/build/";
    uint16_t pixels[416*416];
    int8_t expected[224*224],output[224*224];
    std::ifstream image(std::string(root)+"gray_pixels.bin",std::ios::binary);
    std::ifstream golden(std::string(root)+"gray_expected.bin",std::ios::binary);
    if(!image.read(reinterpret_cast<char*>(pixels),sizeof(pixels)) ||
       !golden.read(reinterpret_cast<char*>(expected),sizeof(expected))) return 1;
    gray_input(pixels,output);
    for(unsigned i=0;i<224*224;++i) if(output[i]!=expected[i]) {
        std::cerr<<"FAIL grayscale bicubic index="<<i<<" got="<<int(output[i])<<" expected="<<int(expected[i])<<std::endl;
        return 1;
    }
    std::cout<<"PASS RGB565 grayscale, Pillow bicubic resize and INT8 quantization: 50176 bytes match"<<std::endl;
    return 0;
}
