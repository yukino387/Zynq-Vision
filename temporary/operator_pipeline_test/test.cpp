#include "../../hardware/hls/src/top.h"
#include <vector>
#include <cstdlib>

static int raw(data_t x) { return x.range(15, 0).to_int(); }

static bool check(int h, int ci, int co, int k, int stride, int act, bool saturate=false) {
    const int oh = h / stride, pixels = oh * oh;
    // The legacy loader reads padding before masking it, including channel 4
    // for the RGB input. Guard storage allows a defined baseline comparison.
    const int guard = h * h * 4 + h * 32 + 32;
    std::vector<data_t> allocation(60000 + 2 * guard + ci * h * h, 0);
    data_t* input = allocation.data() + guard;
    std::vector<data_t> weights(65536 + (co + 32) * (ci + 4) * k * k, 0);
    std::vector<data_t> bias(1024, 0), output(100000 + (co + 32) * pixels, 0);
    std::vector<data_t> output2(output.size(), 0), output3(output.size(), 0), output4(output.size(), 0);
    for (int i = 0; i < ci * h * h; ++i) input[i] = data_t((i * 17 % 101 - 50) / (saturate ? 2.0 : 64.0));
    for (int i = 0; i < co * ci * k * k; ++i) weights[i] = data_t((i * 13 % 29 - 14) / (saturate ? 4.0 : 256.0));
    for (int i = 0; i < co; ++i) bias[i] = data_t((i % 7 - 3) / 64.0);
    conv(input,input,input,input,weights.data(),weights.data(),weights.data(),weights.data(),
         bias.data(),output.data(),output2.data(),output3.data(),output4.data(),ci,co,h,stride,k,act);
    int errors = 0;
    for (int m = 0; m < co; ++m) for (int r = 0; r < oh; ++r) for (int c = 0; c < oh; ++c) {
        data_t acc = bias[m];
        for (int n = 0; n < ci; n += 4) {
            if (k == 3) {
                for (int kr = 0; kr < 3; ++kr) for (int kc = 0; kc < 3; ++kc)
                    for (int j = 0; j < 4; ++j) {
                        int ir = r * stride + kr - 1, ic = c * stride + kc - 1;
                        data_t x = 0, w = 0;
                        if (n+j < ci) {
                            w = weights[(m*ci+n+j)*9+kr*3+kc];
                            if (ir >= 0 && ir < h && ic >= 0 && ic < h) x = input[(n+j)*h*h+ir*h+ic];
                        }
                        data_t product = x * w;
                        acc = data_t(acc + product);
                    }
            } else {
                data_t product[4];
                for (int j = 0; j < 4; ++j)
                    product[j] = data_t(input[(n+j)*h*h+r*h+c] * weights[m*ci+n+j]);
                data_t a = product[0]+product[1], b = product[2]+product[3];
                data_t sum = a+b;
                acc = data_t(acc+sum);
            }
        }
        if (act && acc < data_t(0)) acc = data_t(acc * data_t(0.1));
        const data_t* ports[] = {output.data(), output2.data(), output3.data(), output4.data()};
        const data_t actual = ports[k == 3 ? m % 4 : 0][m*pixels+r*oh+c];
        if (raw(actual) != raw(acc)) {
            if (errors++ < 3) std::cout << "mismatch " << m << ',' << r << ',' << c << '\n';
        }
    }
    std::cout << "CASE h=" << h << " ci=" << ci << " co=" << co << " k=" << k
              << " stride=" << stride << " act=" << act << " saturate=" << saturate << " errors=" << errors << '\n';
    return errors == 0;
}

int main() {
    if (std::getenv("HLS_QUICK_COSIM")) {
        return check(26, 3, 64, 3, 2, 1) && check(13, 8, 16, 1, 1, 1)
               ? EXIT_SUCCESS : EXIT_FAILURE;
    }
    bool ok = true;
    ok &= check(26, 3, 64, 3, 2, 1);
    ok &= check(13, 8, 64, 3, 1, 1);
    ok &= check(26, 8, 32, 3, 1, 0);
    ok &= check(13, 8, 16, 1, 1, 1);
    ok &= check(13, 8, 75, 1, 1, 0);
    ok &= check(26, 8, 75, 1, 1, 0);
    ok &= check(13, 8, 64, 3, 1, 1, true);
    ok &= check(13, 8, 75, 1, 1, 0, true);
    ok &= check(52, 8, 32, 3, 1, 1);
    return ok ? EXIT_SUCCESS : EXIT_FAILURE;
}
