// Scalar INT8 reference inference for the 33-command PL graph.
// Loads the same model.bin as the accelerator and executes every command on
// the CPU, so ARM-only latency can be compared with the PL conv loop.
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>
#ifdef __linux__
#include <sched.h>
#endif

static constexpr unsigned weight_bytes = 6350208;
static constexpr unsigned metadata_words = 16506;
static constexpr unsigned command_count = 33;
static constexpr unsigned feature_bytes = 3012640;
static constexpr unsigned out0_offset = 2910208;
static constexpr unsigned out1_offset = 3005248;

static unsigned pitch(unsigned size) {
    switch (size) {
        case 7: return 8;
        case 14: return 16;
        case 28: return 32;
        case 56: return 64;
        case 112: return 128;
        case 224: return 256;
        default: throw std::runtime_error("Unsupported feature size");
    }
}
static unsigned plane(unsigned size) { return size * pitch(size); }

static inline int8_t requant(int32_t value, int32_t multiplier, int32_t shift) {
    const int64_t product = int64_t(value) * multiplier;
    const uint64_t magnitude = product < 0 ? uint64_t(-product) : uint64_t(product);
    const int64_t rounded = (magnitude + (uint64_t(1) << (shift - 1))) >> shift;
    const int64_t result = product < 0 ? -rounded : rounded;
    return int8_t(result < -127 ? -127 : result > 127 ? 127 : result);
}

static std::vector<uint8_t> read_file(const std::string& path) {
    std::ifstream file(path, std::ios::binary);
    if (!file) throw std::runtime_error("Cannot open " + path);
    file.seekg(0, std::ios::end);
    const auto size = file.tellg();
    file.seekg(0);
    std::vector<uint8_t> data;
    data.resize(size_t(size));
    file.read(reinterpret_cast<char*>(data.data()), size);
    if (!file) throw std::runtime_error("Cannot read " + path);
    return data;
}

// Packing produced by camera/training/pl_model.py pack_weights():
// [co/48][ci/8][lane 4][twelve 12][ci&7][k][k]
static void unpack_weights(const uint8_t* source, unsigned co, unsigned ci, unsigned k,
                           std::vector<int8_t>& destination) {
    const unsigned ci8 = (ci + 7) / 8;
    destination.assign(size_t(co) * ci * k * k, 0);
    const uint8_t* base = source;
    for (unsigned block = 0; block < (co + 47) / 48; ++block) {
        for (unsigned cib = 0; cib < ci8; ++cib) {
            for (unsigned lane = 0; lane < 4; ++lane) {
                for (unsigned twelve = 0; twelve < 12; ++twelve) {
                    const unsigned oc = block * 48 + twelve * 4 + lane;
                    for (unsigned in8 = 0; in8 < 8; ++in8) {
                        const unsigned ic = cib * 8 + in8;
                        const unsigned count = k * k;
                        if (oc < co && ic < ci)
                            std::memcpy(&destination[(size_t(oc) * ci + ic) * count], base, count);
                        base += count;
                    }
                }
            }
        }
    }
}

struct Layer {
    int32_t command[10]{};
    std::vector<int8_t> weight;
    unsigned out_size = 0;
};

static void conv_layer(const Layer& layer, const int8_t* features, const int32_t* metadata) {
    const int32_t* c = layer.command;
    const unsigned ci = unsigned(c[4]), co = unsigned(c[5]), size = unsigned(c[6]);
    const unsigned stride = unsigned(c[7]), k = unsigned(c[8]), act = unsigned(c[9]);
    const unsigned in_pitch = pitch(size), out_pitch = pitch(layer.out_size);
    const int pad = int(k / 2);
    const int8_t* input = features + c[0];
    int8_t* output = const_cast<int8_t*>(features) + c[1];
    const int32_t* bias = metadata + c[3];
    const int32_t* mult = bias + co;
    const int32_t* shift = mult + co;
    const int32_t* neg_mult = shift + co;
    const int32_t* neg_shift = neg_mult + co;
    const unsigned kernel = k * k;

    for (unsigned oc = 0; oc < co; ++oc) {
        const int8_t* w = layer.weight.data() + size_t(oc) * ci * kernel;
        int8_t* out_plane = output + size_t(oc) * plane(layer.out_size);
        for (unsigned oy = 0; oy < layer.out_size; ++oy) {
            const int sy0 = int(oy * stride) - pad;
            for (unsigned ox = 0; ox < layer.out_size; ++ox) {
                const int sx0 = int(ox * stride) - pad;
                int32_t accumulator = bias[oc];
                if (sy0 >= 0 && sx0 >= 0 && sy0 + int(k) <= int(size) && sx0 + int(k) <= int(size)) {
                    for (unsigned ic = 0; ic < ci; ++ic) {
                        const int8_t* in = input + size_t(ic) * plane(size) + size_t(sy0) * in_pitch + sx0;
                        const int8_t* wk = w + ic * kernel;
                        if (k == 3) {
                            accumulator += int32_t(in[0]) * wk[0] + int32_t(in[1]) * wk[1] + int32_t(in[2]) * wk[2]
                                         + int32_t(in[in_pitch]) * wk[3] + int32_t(in[in_pitch + 1]) * wk[4] + int32_t(in[in_pitch + 2]) * wk[5]
                                         + int32_t(in[2 * in_pitch]) * wk[6] + int32_t(in[2 * in_pitch + 1]) * wk[7] + int32_t(in[2 * in_pitch + 2]) * wk[8];
                        } else {
                            accumulator += int32_t(in[0]) * wk[0];
                        }
                    }
                } else {
                    for (unsigned ic = 0; ic < ci; ++ic) {
                        const int8_t* in = input + size_t(ic) * plane(size);
                        const int8_t* wk = w + ic * kernel;
                        for (unsigned ky = 0; ky < k; ++ky) {
                            const int sy = sy0 + int(ky);
                            if (sy < 0 || sy >= int(size)) continue;
                            for (unsigned kx = 0; kx < k; ++kx) {
                                const int sx = sx0 + int(kx);
                                if (sx < 0 || sx >= int(size)) continue;
                                accumulator += int32_t(in[size_t(sy) * in_pitch + sx]) * wk[ky * k + kx];
                            }
                        }
                    }
                }
                const bool negative = act && accumulator < 0;
                out_plane[size_t(oy) * out_pitch + ox] = requant(
                    accumulator, negative ? neg_mult[oc] : mult[oc],
                    negative ? neg_shift[oc] : shift[oc]);
            }
        }
    }
}

static void pool_layer(const int32_t* c, int8_t* features) {
    const unsigned ci = unsigned(c[4]), size = unsigned(c[6]), out_size = size / 2;
    const unsigned in_pitch = pitch(size), out_pitch = pitch(out_size);
    const int8_t* input = features + c[0];
    int8_t* output = features + c[1];
    for (unsigned ch = 0; ch < ci; ++ch) {
        const int8_t* in = input + size_t(ch) * plane(size);
        int8_t* out = output + size_t(ch) * plane(out_size);
        for (unsigned y = 0; y < out_size; ++y) {
            for (unsigned x = 0; x < out_size; ++x) {
                int8_t value = in[size_t(2 * y) * in_pitch + 2 * x];
                value = std::max(value, in[size_t(2 * y) * in_pitch + 2 * x + 1]);
                value = std::max(value, in[size_t(2 * y + 1) * in_pitch + 2 * x]);
                value = std::max(value, in[size_t(2 * y + 1) * in_pitch + 2 * x + 1]);
                out[size_t(y) * out_pitch + x] = value;
            }
        }
    }
}

static void upsample_layer(const int32_t* c, int8_t* features) {
    const unsigned ci = unsigned(c[4]), size = unsigned(c[6]), out_size = size * 2;
    const unsigned in_pitch = pitch(size), out_pitch = pitch(out_size);
    const int8_t* input = features + c[0];
    int8_t* output = features + c[1];
    for (unsigned ch = 0; ch < ci; ++ch) {
        const int8_t* in = input + size_t(ch) * plane(size);
        int8_t* out = output + size_t(ch) * plane(out_size);
        for (unsigned y = 0; y < out_size; ++y) {
            for (unsigned x = 0; x < out_size; ++x) {
                out[size_t(y) * out_pitch + x] = in[size_t(y / 2) * in_pitch + x / 2];
            }
        }
    }
}

static void requant_copy_layer(const int32_t* c, const int32_t* metadata, int8_t* features) {
    const unsigned count = unsigned(c[4]) * plane(unsigned(c[6]));
    const int32_t multiplier = metadata[c[3]], shift = metadata[c[3] + 1];
    const int8_t* input = features + c[0];
    int8_t* output = features + c[1];
    for (unsigned i = 0; i < count; ++i) output[i] = requant(int8_t(input[i]), multiplier, shift);
}

int main(int argc, char** argv) {
    try {
        std::string model_path = "/var/lib/vision/jobs/cmvfi4fsf000quel4l98izgqi/model.bin";
        int runs = 2;
        int cpu = 1;
        std::string output_path = "/tmp/cpu_out.bin";
        for (int i = 1; i < argc; ++i) {
            const std::string arg = argv[i];
            if (arg == "--model" && i + 1 < argc) model_path = argv[++i];
            else if (arg == "--runs" && i + 1 < argc) runs = std::atoi(argv[++i]);
            else if (arg == "--cpu" && i + 1 < argc) cpu = std::atoi(argv[++i]);
            else if (arg == "--out" && i + 1 < argc) output_path = argv[++i];
        }
#ifdef __linux__
        if (cpu >= 0) {
            cpu_set_t set;
            CPU_ZERO(&set);
            CPU_SET(cpu, &set);
            if (sched_setaffinity(0, sizeof(set), &set)) std::perror("sched_setaffinity");
        }
#endif

        const auto file = read_file(model_path);
        if (file.size() != 128 + weight_bytes + metadata_words * 4) throw std::runtime_error("Model size mismatch");
        uint32_t header[4];
        std::memcpy(header, file.data(), sizeof(header));
        if (header[0] != 0x314e4e43u || header[2] != weight_bytes || header[3] != metadata_words * 4)
            throw std::runtime_error("Model header mismatch");
        const uint8_t* weight_bytes_ptr = file.data() + 128;
        const int32_t* metadata = reinterpret_cast<const int32_t*>(file.data() + 128 + weight_bytes);
        const unsigned channels = unsigned(metadata[4]);
        if (channels != 1 && channels != 3) throw std::runtime_error("Unsupported input channels");

        std::vector<Layer> layers(command_count);
        for (unsigned i = 0; i < command_count; ++i) {
            std::memcpy(layers[i].command, metadata + i * 10, sizeof(layers[i].command));
            const int32_t* c = layers[i].command;
            const unsigned k = unsigned(c[8]);
            if (k == 1 || k == 3) {
                unpack_weights(weight_bytes_ptr + c[2], unsigned(c[5]), unsigned(c[4]), k, layers[i].weight);
                layers[i].out_size = unsigned(c[6]) / unsigned(c[7]);
            } else if (k == 2) layers[i].out_size = unsigned(c[6]) / 2;
            else if (k == 0) layers[i].out_size = unsigned(c[6]) * 2;
            else layers[i].out_size = unsigned(c[6]);
        }

        std::vector<int8_t> features(feature_bytes);
        std::vector<int8_t> saved0(1617), saved1(6468);
        printf("CPU_MODEL %s channels=%u runs=%d cpu=%d\n", model_path.c_str(), channels, runs, cpu);
        for (int run = 0; run < runs; ++run) {
            std::memset(features.data(), 0, features.size());
            for (unsigned c = 0; c < channels; ++c)
                for (unsigned y = 0; y < 224; ++y)
                    for (unsigned x = 0; x < 224; ++x)
                        features[c * plane(224) + y * pitch(224) + x] =
                            int8_t(int(x * 17 + y * 31 + c * 47 + 13) % 251 - 125);
            uint64_t layer_ns[command_count]{};
            const auto begin = std::chrono::steady_clock::now();
            for (unsigned i = 0; i < command_count; ++i) {
                const auto layer_begin = std::chrono::steady_clock::now();
                const int32_t* c = layers[i].command;
                const unsigned k = unsigned(c[8]);
                if (k == 1 || k == 3) conv_layer(layers[i], features.data(), metadata);
                else if (k == 2) pool_layer(c, features.data());
                else if (k == 0) upsample_layer(c, features.data());
                else if (k == 5) requant_copy_layer(c, metadata, features.data());
                else throw std::runtime_error("Unsupported kernel");
                layer_ns[i] = std::chrono::duration_cast<std::chrono::nanoseconds>(
                    std::chrono::steady_clock::now() - layer_begin).count();
            }
            const auto elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(
                std::chrono::steady_clock::now() - begin).count();
            printf("CPU_RUN %d totalMs=%.3f\n", run, double(elapsed) / 1e6);
            for (unsigned i = 0; i < command_count; ++i)
                printf("CPU_LAYER %u kernel=%d channels=%d size=%d ms=%.3f\n",
                       i, layers[i].command[8], layers[i].command[5],
                       layers[i].command[6], double(layer_ns[i]) / 1e6);
            const int8_t* raw0 = features.data() + out0_offset;
            const int8_t* raw1 = features.data() + out1_offset;
            for (unsigned i = 0; i < 1617; ++i) saved0[i] = raw0[(i / 7) * 8 + i % 7];
            for (unsigned i = 0; i < 6468; ++i) saved1[i] = raw1[(i / 14) * 16 + i % 14];
        }
        std::ofstream out(output_path, std::ios::binary);
        out.write(reinterpret_cast<const char*>(saved0.data()), saved0.size());
        out.write(reinterpret_cast<const char*>(saved1.data()), saved1.size());
        printf("CPU_OUT %s out0=%zu out1=%zu\n", output_path.c_str(), saved0.size(), saved1.size());
    } catch (const std::exception& error) {
        fprintf(stderr, "CPU_ERROR %s\n", error.what());
        return 1;
    }
    return 0;
}
