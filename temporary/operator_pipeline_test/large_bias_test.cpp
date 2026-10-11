#include "../../hardware/hls/src/top.h"
#include <algorithm>
#include <vector>

static bool check(int kernel, int h=13, int ci=4, int co=512, int stride=1, int act=0) {
    const int oh=h/stride, pixels=oh*oh;
    std::vector<data_t> input(std::max(60000,4*h*h), 0), weight(65536, 0), bias(1024, 0);
    const data_t sentinel = data_t(31);
    std::vector<data_t> output[4];
    for (auto& port : output) port.assign(std::max(100000,co*pixels+64), sentinel);
    for (int i = 0; i < h*h; ++i) input[i] = data_t((i%31)/32.0);
    for (int m = 0; m < co; ++m) {
        bias[m] = data_t((m%37-18)/64.0);
        weight[m*ci*kernel*kernel + (kernel == 3 ? 4 : 0)] = data_t(1);
    }
    conv(input.data(), input.data(), input.data(), input.data(),
         weight.data(), weight.data(), weight.data(), weight.data(), bias.data(),
         output[0].data(), output[1].data(), output[2].data(), output[3].data(),
         ci, co, h, stride, kernel, act);
    int errors = 0;
    for (int m = 0; m < co; ++m) for (int r = 0; r < oh; ++r) for (int c = 0; c < oh; ++c) {
        data_t expected = data_t(input[r*stride*h+c*stride] + bias[m]);
        if (act && expected < data_t(0)) expected = data_t(expected*data_t(0.1));
        if (output[m%4][m*pixels+r*oh+c].range(15,0) != expected.range(15,0)) ++errors;
    }
    for (const auto& port : output)
        for (int i = co*pixels; i < static_cast<int>(port.size()); ++i)
            if (port[i].range(15,0) != sentinel.range(15,0)) ++errors;
    std::cout << "C_ONLY h=" << h << " ci=" << ci << " co=" << co << " kernel=" << kernel << " stride=" << stride << " act=" << act << " errors=" << errors << '\n';
    return errors == 0;
}

int main() {
    bool ok = check(3);
    ok &= check(1);
    ok &= check(3,416,3,32,2,1);
    return ok ? 0 : 1;
}
