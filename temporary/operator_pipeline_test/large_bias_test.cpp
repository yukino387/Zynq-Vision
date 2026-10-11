#include "../../hardware/hls/src/top.h"
#include <vector>

static bool check(int kernel) {
    const int h = 13, pixels = h*h, ci = 4, co = 512;
    std::vector<data_t> input(60000, 0), weight(65536, 0), bias(1024, 0);
    const data_t sentinel = data_t(31);
    std::vector<data_t> output[4];
    for (auto& port : output) port.assign(100000, sentinel);
    for (int i = 0; i < pixels; ++i) input[i] = data_t((i%31)/32.0);
    for (int m = 0; m < co; ++m) {
        bias[m] = data_t((m%37-18)/64.0);
        weight[m*ci*kernel*kernel + (kernel == 3 ? 4 : 0)] = data_t(1);
    }
    conv(input.data(), input.data(), input.data(), input.data(),
         weight.data(), weight.data(), weight.data(), weight.data(), bias.data(),
         output[0].data(), output[1].data(), output[2].data(), output[3].data(),
         ci, co, h, 1, kernel, 0);
    int errors = 0;
    for (int m = 0; m < co; ++m) for (int i = 0; i < pixels; ++i) {
        const data_t expected = data_t(input[i] + bias[m]);
        if (output[m%4][m*pixels+i].range(15,0) != expected.range(15,0)) ++errors;
    }
    for (const auto& port : output)
        for (int i = co*pixels; i < 100000; ++i)
            if (port[i].range(15,0) != sentinel.range(15,0)) ++errors;
    std::cout << "C_ONLY bias-tail co=512 kernel=" << kernel << " errors=" << errors << '\n';
    return errors == 0;
}

int main() {
    bool ok = check(3);
    ok &= check(1);
    return ok ? 0 : 1;
}
