#pragma once
#include "core.h"
#include <array>
#include <cstdint>
#include <string>
#include <vector>

namespace terminal {
// Compatibility for the delivered liquid-level package, not a new model format.
inline constexpr const char* level_model_sha256="3aca8253f829d85562fa3952a70df36e756fbecc399b30ebc5c4e08e983ab065";
// LEVEL-ROW-v1.3 pass band on the normalized 224-row image: good bottles measure
// 91.2~96.1, underfilled ones 108.5~110.0.
inline constexpr double level_band_low=85.0,level_band_high=102.9;
struct LevelFrame {
    bool active=false,label_found=false,fallback=false;
    std::array<int,4> bbox{},crop{};
    double label_top=0,label_height=0,row=-1,strength=0;
    int resized_width=0;
    std::vector<uint8_t> gray;
};
LevelFrame prepare_level_bgr(const uint8_t* bgr,unsigned width,unsigned height);
LevelFrame prepare_level_rgb565(const uint16_t* pixels);
void measure_level(LevelFrame&);
FilterResult level_detections(FilterResult,const LevelFrame&);
Decision level_decision(const Rules&,const FilterResult&,const LevelFrame&,bool quality_pass);
const char* level_status(const LevelFrame&,bool target);
}
