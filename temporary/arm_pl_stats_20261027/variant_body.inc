// Included once per measurement variant.  The caller defines:
//   VNS    namespace holding one build of the scalar reference source
//   VB_FN  name of the layer-building helper for this build
//   VF_FN  name of the timed forward helper for this build
static std::vector<VNS::Layer> VB_FN(const std::vector<uint8_t>& file, const int32_t* metadata,
                                    uint64_t& macs) {
    using namespace VNS;
    std::vector<Layer> layers(command_count);
    for (unsigned i = 0; i < command_count; ++i) {
        std::memcpy(layers[i].command, metadata + i * 10, sizeof(layers[i].command));
        const int32_t* c = layers[i].command;
        const unsigned k = unsigned(c[8]);
        layers[i].out_size = k == 0 ? unsigned(c[6]) * 2
                            : k == 2 ? unsigned(c[6]) / 2
                            : (k == 1 || k == 3) ? unsigned(c[6]) / unsigned(c[7]) : unsigned(c[6]);
        if (k == 1 || k == 3) {
            unpack_weights(file.data() + 128 + c[2], unsigned(c[5]), unsigned(c[4]), k,
                           layers[i].weight);
            macs += uint64_t(layers[i].out_size) * layers[i].out_size * unsigned(c[4]) *
                    unsigned(c[5]) * k * k;
        }
    }
    return layers;
}

// One timed forward pass.  Buffer zeroing and input row copy happen before the
// timed region, exactly as in the PL path.
static void VF_FN(const std::vector<VNS::Layer>& layers, const int32_t* metadata,
                  const std::vector<int8_t>& input, unsigned channels,
                  std::vector<int8_t>& features, std::vector<int8_t>& output,
                  uint64_t& total_ns, std::vector<uint64_t>& layer_ns) {
    using namespace VNS;
    std::fill(features.begin(), features.end(), 0);
    for (unsigned c = 0; c < channels; ++c)
        for (unsigned y = 0; y < 224; ++y)
            std::memcpy(features.data() + c * plane(224) + y * pitch(224),
                        input.data() + size_t(c) * 224 * 224 + size_t(y) * 224, 224);
    layer_ns.assign(command_count, 0);
    const auto begin = std::chrono::steady_clock::now();
    for (unsigned i = 0; i < command_count; ++i) {
        const auto start = std::chrono::steady_clock::now();
        const int32_t* c = layers[i].command;
        const unsigned k = unsigned(c[8]);
        if (k == 1 || k == 3) conv_layer(layers[i], features.data(), metadata);
        else if (k == 2) pool_layer(c, features.data());
        else if (k == 0) upsample_layer(c, features.data());
        else if (k == 5) requant_copy_layer(c, metadata, features.data());
        else throw std::runtime_error("Unsupported operator");
        layer_ns[i] = uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now() - start).count());
    }
    total_ns = uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now() - begin).count());
    output.assign(8085, 0);
    for (unsigned i = 0; i < 1617; ++i) output[i] = features[out0_offset + (i / 7) * 8 + i % 7];
    for (unsigned i = 0; i < 6468; ++i) output[1617 + i] = features[out1_offset + (i / 14) * 16 + i % 14];
}
