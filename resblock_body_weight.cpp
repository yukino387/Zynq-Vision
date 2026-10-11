#include "resblock_body.h"

bool Resblock_body::load_weight(const char* directory, BasicConv::WeightFileReader reader,
                                void* context) {
    return conv1->load_weight_files(directory, "w1.bin", "b1.bin", reader, context) &&
           conv2->load_weight_files(directory, "w2.bin", "b2.bin", reader, context) &&
           conv3->load_weight_files(directory, "w3.bin", "b3.bin", reader, context) &&
           conv4->load_weight_files(directory, "w4.bin", "b4.bin", reader, context);
}
