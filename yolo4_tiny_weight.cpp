#include "yolo4_tiny.h"
#include "weight_loading.h"

bool Yolo4_Tiny::load_weight(const char* directory, BasicConv::WeightFileReader reader,
                            void* context) {
    if (!directory || !*directory) return false;
    const WeightDirectory headP4(directory, "yolo_headP4");
    const WeightDirectory headP5(directory, "yolo_headP5");
    return backbone->load_weight(directory, reader, context) &&
           conv_forP5_conv->load_weight(WeightDirectory(directory, "conv_forP5").c_str(), reader, context) &&
           yolo_headP4_basic_conv1->load_weight_files(headP4.c_str(), "w1.bin", "b1.bin", reader, context) &&
           load_weight_pair(headP4.c_str(), "w2.bin", "b2.bin", yolo_headP4_w2,
                            OUT_CH * 256, yolo_headP4_b2, OUT_CH, reader, context) &&
           yolo_headP5_basic_conv1->load_weight_files(headP5.c_str(), "w1.bin", "b1.bin", reader, context) &&
           load_weight_pair(headP5.c_str(), "w2.bin", "b2.bin", yolo_headP5_w2,
                            OUT_CH * 512, yolo_headP5_b2, OUT_CH, reader, context) &&
           upsample_conv->load_weight(WeightDirectory(directory, "upsample").c_str(), reader, context);
}
