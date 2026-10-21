#pragma once
#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace terminal {
enum class Result { Pass, Fail, Review, Error };
const char* name(Result result);
bool product_classes_match(const std::vector<std::string>& product, const std::vector<std::string>& model);
struct Box { unsigned class_id; double confidence, x1, y1, x2, y2; unsigned track_id=0; bool track_confirmed=false; };
struct Postprocess {
    double nms_iou=.45,containment=.9,min_area=.00002,track_iou=.3;
    unsigned max_detections=100,track_min_hits=2,track_max_misses=3,track_max_gap_ms=1000;
    unsigned algorithm_version=3;
};
struct FilterResult {
    std::vector<Box> boxes;
    unsigned candidates=0,invalid=0,tiny=0,nested=0,suppressed=0;
    bool overflow=false;
};
FilterResult filter_boxes(const std::vector<Box>&,const Postprocess& = {});
FilterResult detect_objects(const int8_t* out0,const int8_t* out1,const Postprocess& = {});
class Tracker {
    struct Track {
        Box box;
        unsigned id,hits,misses;
        uint64_t last_ns;
        double vx=0,vy=0;
        bool moving=false,has_appearance=false;
        std::array<double,19> appearance{};
    };
    std::vector<Track> tracks;
    unsigned next_id=1;
    uint64_t last_ns=0;
public:
    void reset();
    void update(std::vector<Box>&,uint64_t monotonic_ns,const Postprocess&,const uint16_t* pixels=nullptr,double confidence=.7);
};
struct Check { unsigned class_id, minimum, maximum; bool positioned=false; std::array<double,4> region={0,0,1,1}; };
struct Rules {
    unsigned classes = 0;
    std::array<double, 4> region = {0, 0, 1, 1};
    double confidence = .7;
    bool quality_gate = true;
    std::vector<Check> checks;
    Postprocess postprocess;
};
struct Finding { Check check; unsigned count, uncertain; Result result; };
struct Decision { Result result = Result::Review; std::vector<Finding> findings; unsigned outside = 0; };
Decision evaluate(const Rules&, const std::vector<Box>&, bool has_output, bool quality_pass, unsigned error = 0);
std::vector<Box> detect(const int8_t* out0, const int8_t* out1);
bool quality(const uint16_t* rgb565);
std::string sha256(const void* data, unsigned size);
}
