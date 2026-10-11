#include "basic_conv.h"
#include "weight_loading.h"
#include "xil_cache.h"
#include <cmath>
#include <cstdio>
#include <cstring>
#include <new>

static bool read_pc_file(const char* path, float* values, std::size_t count, void*) {
    FILE* file = std::fopen(path, "rb");
    if (!file) return false;
    const bool complete = std::fread(values, sizeof(float), count, file) == count;
    const bool exact = complete && std::fgetc(file) == EOF && !std::ferror(file);
    const bool closed = std::fclose(file) == 0;
    return exact && closed;
}

static bool quantize(const float* values, data_t* result, std::size_t count) {
    static_assert(sizeof(data_t) == 2, "Expected 16-bit data_t");
    for (std::size_t i = 0; i < count; ++i) {
        // Match the author's float multiplication and round-away-from-zero rule.
        const float rounded = std::round(values[i] * 512.0f);
        if (!std::isfinite(rounded) || rounded < -32768.0f || rounded > 32767.0f)
            return false;
        result[i] = static_cast<data_t>(rounded);
    }
    return true;
}

bool BasicConv::load_weight(const char* directory, WeightFileReader reader, void* context) {
    return load_weight_files(directory, "w.bin", "b.bin", reader, context);
}

bool BasicConv::load_weight_files(const char* directory, const char* weight_file,
                                const char* bias_file, WeightFileReader reader, void* context) {
    if (ch_in <= 0 || ch_out <= 0 || k <= 0) return false;
    return load_weight_pair(directory, weight_file, bias_file, weight,
                            static_cast<std::size_t>(ch_out) * ch_in * k * k,
                            bias, static_cast<std::size_t>(ch_out), reader, context);
}

bool load_weight_pair(const char* directory, const char* weight_file, const char* bias_file,
                      data_t* weight, std::size_t weights, data_t* bias, std::size_t biases,
                      BasicConv::WeightFileReader reader, void* context) {
    if (!directory || !*directory || !weight_file || !*weight_file ||
        !bias_file || !*bias_file || !weight || !bias || !weights || !biases) return false;
    if (!reader) reader = read_pc_file;
    const std::size_t length = std::strlen(directory);
    const std::size_t weight_length = std::strlen(weight_file);
    const std::size_t bias_length = std::strlen(bias_file);
    char* path = new (std::nothrow) char[length +
        (weight_length > bias_length ? weight_length : bias_length) + 2];
    float* raw = new (std::nothrow) float[weights + biases];
    data_t* converted = new (std::nothrow) data_t[weights + biases];
    if (!path || !raw || !converted) {
        delete[] path;
        delete[] raw;
        delete[] converted;
        return false;
    }
    std::memcpy(path, directory, length);
    const bool has_separator = directory[length - 1] == '/' || directory[length - 1] == '\\';
    const std::size_t suffix = length + (has_separator ? 0 : 1);
    if (!has_separator) path[length] = '/';
    std::strcpy(path + suffix, weight_file);
    bool success = reader(path, raw, weights, context);
    std::strcpy(path + suffix, bias_file);
    success = success && reader(path, raw + weights, biases, context);
    success = success && quantize(raw, converted, weights + biases);
    if (success) {
        std::memcpy(weight, converted, weights * sizeof(data_t));
        std::memcpy(bias, converted + weights, biases * sizeof(data_t));
        Xil_DCacheFlushRange(reinterpret_cast<INTPTR>(weight), weights * sizeof(data_t));
        Xil_DCacheFlushRange(reinterpret_cast<INTPTR>(bias), biases * sizeof(data_t));
    }
    delete[] path;
    delete[] raw;
    delete[] converted;
    return success;
}
