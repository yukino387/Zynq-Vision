#include "cspdarknet.h"
#include "weight_loading.h"

bool CSPDarkNet::load_weight(const char* directory, BasicConv::WeightFileReader reader,
                             void* context) {
    if (!directory || !*directory) return false;
    return basic_conv1->load_weight(WeightDirectory(directory, "BasicConv1").c_str(), reader, context) &&
           basic_conv2->load_weight(WeightDirectory(directory, "BasicConv2").c_str(), reader, context) &&
           basic_conv3->load_weight(WeightDirectory(directory, "BasicConv3").c_str(), reader, context) &&
           resblock1->load_weight(WeightDirectory(directory, "ResBlock1").c_str(), reader, context) &&
           resblock2->load_weight(WeightDirectory(directory, "ResBlock2").c_str(), reader, context) &&
           resblock3->load_weight(WeightDirectory(directory, "ResBlock3").c_str(), reader, context);
}
