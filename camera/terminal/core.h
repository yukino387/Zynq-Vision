#pragma once
#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace terminal {
enum class Result { Pass, Fail, Review, Error };
const char* name(Result result);
bool product_classes_match(const std::vector<std::string>& product, const std::vector<std::string>& model);
struct Box { unsigned class_id; double confidence, x1, y1, x2, y2; };
struct Check { unsigned class_id, minimum, maximum; bool positioned=false; std::array<double,4> region={0,0,1,1}; };
struct Rules {
    unsigned classes = 0;
    std::array<double, 4> region = {0, 0, 1, 1};
    double confidence = .7;
    bool quality_gate = true;
    std::vector<Check> checks;
};
struct Finding { Check check; unsigned count, uncertain; Result result; };
struct Decision { Result result = Result::Review; std::vector<Finding> findings; unsigned outside = 0; };
Decision evaluate(const Rules&, const std::vector<Box>&, bool has_output, bool quality_pass, unsigned error = 0);
std::vector<Box> detect(const int8_t* out0, const int8_t* out1);
bool quality(const uint16_t* rgb565);
std::string sha256(const void* data, unsigned size);
}
