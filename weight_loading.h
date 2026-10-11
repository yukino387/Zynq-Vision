#ifndef WEIGHT_LOADING_H
#define WEIGHT_LOADING_H

#include "basic_conv.h"
#include <cstring>
#include <new>

class WeightDirectory {
public:
    WeightDirectory(const char* directory, const char* name) : path(nullptr) {
        if (!directory || !*directory || !name) return;
        const std::size_t length = std::strlen(directory);
        path = new (std::nothrow) char[length + std::strlen(name) + 2];
        if (!path) return;
        std::memcpy(path, directory, length);
        const bool separated = directory[length - 1] == '/' || directory[length - 1] == '\\';
        if (!separated) path[length] = '/';
        std::strcpy(path + length + (separated ? 0 : 1), name);
    }
    ~WeightDirectory() { delete[] path; }
    const char* c_str() const { return path; }
    WeightDirectory(const WeightDirectory&) = delete;
    WeightDirectory& operator=(const WeightDirectory&) = delete;
private:
    char* path;
};

// Each pair is committed only after exact-size reads and successful quantization.
bool load_weight_pair(const char* directory, const char* weight_file,
                      const char* bias_file, data_t* weight, std::size_t weights,
                      data_t* bias, std::size_t biases,
                      BasicConv::WeightFileReader reader = nullptr, void* context = nullptr);

#endif
