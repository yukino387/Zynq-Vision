// Statistical ARM versus PL benchmark for one Zynq-7020 board.
//
// Four measurement conditions share this harness, one model and one input set:
//   arm_o0     the shipped scalar reference source compiled with -O0 (no optimisation)
//   arm_novec  the same source at -O3 with autovectorisation disabled: this is the
//              PS code path the project actually ships
//   arm_vec    the same source at -O3 with autovectorisation enabled (NEON allowed)
//   pl         the 48x8 INT8 accelerator reached through the deployed bitstream
//
// All four execute the identical 33-command graph and must reproduce identical
// 8085 INT8 output bytes, so observed differences are implementation differences
// and not arithmetic differences.  Trials are emitted in randomly interleaved
// rounds so that every condition samples the same thermal / clock window.
#include <nlohmann/json.hpp>
#include "hardware.h"
#include "C:/00_workplace/fpga/cnn_accelerator/camera/terminal/core.h"
#include "C:/00_workplace/fpga/cnn_accelerator/camera/int8/gray.h"
#include <algorithm>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <map>
#include <random>
#include <sched.h>
#include <stdexcept>
#include <string>
#include <vector>
#include <arm_neon.h>

// ---- variant 1: unoptimised build of the shipped scalar reference -----------
#pragma GCC push_options
#pragma GCC optimize("O0")
namespace v_o0 {
#define main reference_main_o0
#include "scalar_reference.cpp"
#undef main
}
#pragma GCC pop_options

// ---- variant 2: -O3, autovectorisation disabled (shipped PS reference) ------
#pragma GCC push_options
#pragma GCC optimize("no-tree-vectorize,no-tree-slp-vectorize")
namespace v_novec {
#define main reference_main_novec
#include "scalar_reference.cpp"
#undef main
}
#pragma GCC pop_options

// ---- variant 3: -O3 with autovectorisation allowed --------------------------
namespace v_vec {
#define main reference_main_vec
#include "scalar_reference.cpp"
#undef main
}

namespace REF = v_novec;
static constexpr unsigned WBYTES = REF::weight_bytes;
static constexpr unsigned META_WORDS = REF::metadata_words;
static constexpr unsigned CMDS = REF::command_count;
static constexpr unsigned FEATURE_BYTES = REF::feature_bytes;

static std::vector<uint8_t> read_all(const std::string& path) {
    std::ifstream file(path, std::ios::binary);
    if (!file) throw std::runtime_error("Cannot open " + path);
    file.seekg(0, std::ios::end);
    const auto size = file.tellg();
    file.seekg(0);
    std::vector<uint8_t> data(static_cast<size_t>(size));
    file.read(reinterpret_cast<char*>(data.data()), size);
    if (!file) throw std::runtime_error("Cannot read " + path);
    return data;
}

static uint64_t now_ns() {
    return uint64_t(std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count());
}

static std::string read_text(const std::string& path) {
    std::ifstream file(path);
    if (!file) return std::string();
    std::string text((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
    while (!text.empty() && (text.back() == '\n' || text.back() == '\r' || text.back() == ' ')) text.pop_back();
    return text;
}

#define VNS v_o0
#define VB_FN build_layers_o0
#define VF_FN arm_forward_o0
#include "variant_body.inc"
#undef VNS
#undef VB_FN
#undef VF_FN

#define VNS v_novec
#define VB_FN build_layers_novec
#define VF_FN arm_forward_novec
#include "variant_body.inc"
#undef VNS
#undef VB_FN
#undef VF_FN

#define VNS v_vec
#define VB_FN build_layers_vec
#define VF_FN arm_forward_vec
#include "variant_body.inc"
#undef VNS
#undef VB_FN
#undef VF_FN


// ---- microkernel calibration -------------------------------------------------
// Two hand-written inner products over the same INT8 data.  They measure the
// issue-rate ceiling of this core for INT8 multiply-accumulate with no memory
// traffic, which is what a roofline comparison needs.  The scalar variant is
// pinned to a non-vectorising optimisation level so that it really stays scalar.
__attribute__((noinline, optimize("no-tree-vectorize,no-tree-slp-vectorize")))
static uint32_t calibrate_scalar(const int8_t* a, const int8_t* b, unsigned n, unsigned reps) {
    uint32_t checksum = 0;
    for (unsigned r = 0; r < reps; ++r) {
        int32_t acc = 0;
        for (unsigned i = 0; i < n; ++i) acc += int32_t(a[i]) * int32_t(b[i]);
        checksum = checksum * 31u + uint32_t(acc);
    }
    return checksum;
}

__attribute__((noinline))
static uint32_t calibrate_neon(const int8_t* a, const int8_t* b, unsigned n, unsigned reps) {
    uint32_t checksum = 0;
    for (unsigned r = 0; r < reps; ++r) {
        int32x4_t s0 = vdupq_n_s32(0), s1 = vdupq_n_s32(0), s2 = vdupq_n_s32(0), s3 = vdupq_n_s32(0);
        unsigned i = 0;
        for (; i + 32 <= n; i += 32) {
            const int8x16_t va0 = vld1q_s8(a + i), vb0 = vld1q_s8(b + i);
            const int8x16_t va1 = vld1q_s8(a + i + 16), vb1 = vld1q_s8(b + i + 16);
            const int16x8_t a0 = vmovl_s8(vget_low_s8(va0)), b0 = vmovl_s8(vget_low_s8(vb0));
            const int16x8_t a1 = vmovl_s8(vget_high_s8(va0)), b1 = vmovl_s8(vget_high_s8(vb0));
            const int16x8_t a2 = vmovl_s8(vget_low_s8(va1)), b2 = vmovl_s8(vget_low_s8(vb1));
            const int16x8_t a3 = vmovl_s8(vget_high_s8(va1)), b3 = vmovl_s8(vget_high_s8(vb1));
            s0 = vmlal_s16(s0, vget_low_s16(a0), vget_low_s16(b0));
            s1 = vmlal_s16(s1, vget_high_s16(a0), vget_high_s16(b0));
            s2 = vmlal_s16(s2, vget_low_s16(a1), vget_low_s16(b1));
            s3 = vmlal_s16(s3, vget_high_s16(a1), vget_high_s16(b1));
            s0 = vmlal_s16(s0, vget_low_s16(a2), vget_low_s16(b2));
            s1 = vmlal_s16(s1, vget_high_s16(a2), vget_high_s16(b2));
            s2 = vmlal_s16(s2, vget_low_s16(a3), vget_low_s16(b3));
            s3 = vmlal_s16(s3, vget_high_s16(a3), vget_high_s16(b3));
        }
        int32_t rest = 0;
        for (; i < n; ++i) rest += int32_t(a[i]) * int32_t(b[i]);
        int32_t lanes[4];
        vst1q_s32(lanes, vaddq_s32(vaddq_s32(s0, s1), vaddq_s32(s2, s3)));
        const int32_t acc = lanes[0] + lanes[1] + lanes[2] + lanes[3] + rest;
        checksum = checksum * 31u + uint32_t(acc);
    }
    return checksum;
}

using json = nlohmann::json;

int main(int argc, char** argv) {
    try {
        if (argc != 5) throw std::runtime_error("Usage: bench_stat MODEL MANIFEST OUT_DIR SCHEDULE");
        const std::string out_dir = argv[3];
        std::filesystem::create_directories(out_dir);
        cpu_set_t set;
        CPU_ZERO(&set);
        CPU_SET(1, &set);
        if (sched_setaffinity(0, sizeof(set), &set)) throw std::runtime_error("CPU affinity failed");

        const auto file = read_all(argv[1]);
        if (file.size() != size_t(128 + WBYTES + META_WORDS * 4)) throw std::runtime_error("Model size mismatch");
        const auto* metadata = reinterpret_cast<const int32_t*>(file.data() + 128 + WBYTES);
        const unsigned channels = unsigned(metadata[4]);
        if (channels != 1 && channels != 3) throw std::runtime_error("Unsupported input channels");
        const std::string version(reinterpret_cast<const char*>(file.data() + 24));

        json manifest = json::parse(read_text(argv[2]));
        json schedule = json::parse(read_text(argv[4]));
        const uint64_t seed = schedule.value("seed", 20261027ull);
        const uint64_t budget_ms = schedule.value("budgetMs", 1500000ull);

        terminal::Hardware hw;
        hw.load_model(file, version, terminal::sha256(file.data() + 128, file.size() - 128),
                      terminal::sha256(file.data(), file.size()));

        uint64_t macs_o0 = 0, macs_novec = 0, macs_vec = 0;
        const auto layers_o0 = build_layers_o0(file, metadata, macs_o0);
        const auto layers_novec = build_layers_novec(file, metadata, macs_novec);
        const auto layers_vec = build_layers_vec(file, metadata, macs_vec);
        if (macs_o0 != macs_novec || macs_novec != macs_vec) throw std::runtime_error("MAC count differs between variants");

        std::vector<int8_t> feat_o0(FEATURE_BYTES), feat_novec(FEATURE_BYTES), feat_vec(FEATURE_BYTES);

        std::map<std::string, json> case_meta;
        for (const auto& c : manifest["cases"]) case_meta[c["name"].get<std::string>()] = c;

        std::ofstream trials_csv(out_dir + "/raw_trials.csv");
        std::ofstream layers_csv(out_dir + "/raw_layers.csv");
        trials_csv << "phase,input,condition,round,task_index,start_monotonic_ns,duration_ns,output_sha256\n";
        layers_csv << "phase,input,condition,round,task_index,layer_index,duration_ns\n";
        std::ofstream cal_csv(out_dir + "/raw_calibration.csv");
        cal_csv << "phase,kernel,round,n,reps,duration_ns,checksum\n";

        json meta = {{"modelVersion", version},
                     {"modelSha256", terminal::sha256(file.data(), file.size())},
                     {"inputChannels", channels},
                     {"macs", macs_novec},
                     {"commandCount", CMDS},
                     {"cpuPin", 1},
                     {"seed", seed},
                     {"budgetMs", budget_ms},
                     {"schedule", schedule},
                     {"outputBytes", 8085},
                     {"scope", "33 operators; PL includes PS register programming and completion polling; both paths exclude model load, input preparation and output extraction"},
                     {"variants", {{"arm_o0", "shipped scalar reference source, -O0, no optimisation"},
                                   {"arm_novec", "shipped scalar reference source, -O3, autovectorisation disabled"},
                                   {"arm_vec", "same source, -O3, autovectorisation enabled (NEON allowed)"},
                                   {"pl", "48x8 INT8 accelerator, deployed bitstream"}}},
                     {"cpuFreqKHzStart", read_text("/sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq")},
                     {"thermalStart", read_text("/sys/class/thermal/thermal_zone0/temp")},
                     {"wallStartNs", now_ns()},
                     {"truncated", false}};

        std::mt19937_64 rng(seed);
        std::vector<int8_t> input, reference_output;
        std::map<std::string, uint64_t> counts;
        const uint64_t run_begin = now_ns();
        bool truncated = false;

        auto execute = [&](const std::string& phase, const std::string& input_name, int round,
                           int task_index, const std::string& cond, bool record) {
            uint64_t ns = 0;
            std::vector<uint64_t> layer_ns;
            std::vector<int8_t> output;
            const uint64_t start = now_ns();
            if (cond == "pl") output = hw.fixed_forward(input, ns, layer_ns);
            else if (cond == "arm_novec") arm_forward_novec(layers_novec, metadata, input, channels, feat_novec, output, ns, layer_ns);
            else if (cond == "arm_vec") arm_forward_vec(layers_vec, metadata, input, channels, feat_vec, output, ns, layer_ns);
            else if (cond == "arm_o0") arm_forward_o0(layers_o0, metadata, input, channels, feat_o0, output, ns, layer_ns);
            else throw std::runtime_error("Unknown condition " + cond);
            if (reference_output.empty()) reference_output = output;
            else if (output != reference_output) throw std::runtime_error("INT8 output mismatch: " + cond + " on " + input_name);
            if (!record) return;
            const std::string sha = terminal::sha256(output.data(), output.size());
            ++counts[cond];
            trials_csv << phase << ',' << input_name << ',' << cond << ',' << round << ','
                       << task_index << ',' << start << ',' << ns << ',' << sha << '\n';
            trials_csv.flush();
            for (unsigned i = 0; i < layer_ns.size(); ++i)
                layers_csv << phase << ',' << input_name << ',' << cond << ',' << round << ','
                           << task_index << ',' << i << ',' << layer_ns[i] << '\n';
            layers_csv.flush();
            printf("BENCH_TRIAL %s %s %s round=%d ms=%.3f\n", phase.c_str(), input_name.c_str(),
                   cond.c_str(), round, double(ns) / 1e6);
            fflush(stdout);
        };

        for (const auto& phase : schedule["phases"]) {
            if (truncated) break;
            const std::string phase_name = phase["name"].get<std::string>();
            if (phase.value("kind", std::string("network")) == "calibration") {
                const int cal_rounds = phase["rounds"].get<int>();
                const unsigned n = phase["n"].get<unsigned>();
                const unsigned reps_scalar = phase["repsScalar"].get<unsigned>();
                const unsigned reps_neon = phase["repsNeon"].get<unsigned>();
                std::vector<int8_t> ca(n), cb(n);
                std::mt19937 cgen{unsigned(seed)};
                std::uniform_int_distribution<int> dist(-127, 127);
                for (auto& v : ca) v = int8_t(dist(cgen));
                for (auto& v : cb) v = int8_t(dist(cgen));
                if (calibrate_scalar(ca.data(), cb.data(), n, 1) != calibrate_neon(ca.data(), cb.data(), n, 1))
                    throw std::runtime_error("Microkernel checksum mismatch: scalar and NEON disagree");
                for (int round = 0; round < cal_rounds; ++round) {
                    std::vector<std::string> order = {"scalar", "neon"};
                    std::shuffle(order.begin(), order.end(), rng);
                    for (const auto& kernel : order) {
                        const unsigned reps = kernel == "scalar" ? reps_scalar : reps_neon;
                        const uint64_t start = now_ns();
                        const uint32_t sum = kernel == "scalar" ? calibrate_scalar(ca.data(), cb.data(), n, reps)
                                                                : calibrate_neon(ca.data(), cb.data(), n, reps);
                        const uint64_t ns = now_ns() - start;
                        cal_csv << phase_name << ',' << kernel << ',' << round << ',' << n << ',' << reps
                                << ',' << ns << ',' << sum << '\n';
                        cal_csv.flush();
                        printf("BENCH_CAL %s %s round=%d n=%u reps=%u ns=%llu\n", phase_name.c_str(),
                               kernel.c_str(), round, n, reps, (unsigned long long)ns);
                        fflush(stdout);
                    }
                }
                printf("BENCH_CAL_DONE %s\n", phase_name.c_str());
                fflush(stdout);
                continue;
            }
            std::vector<std::string> inputs = phase["inputs"].get<std::vector<std::string>>();
            if (phase.value("permuteInputs", false)) std::shuffle(inputs.begin(), inputs.end(), rng);
            const int rounds = phase["rounds"];
            const int pl_per_round = phase["plPerRound"];
            const std::vector<std::string> arm_conditions = phase["armConditions"].get<std::vector<std::string>>();
            const auto warmup = phase["warmup"];

            for (const auto& input_name : inputs) {
                if (truncated) break;
                const auto& spec = case_meta.at(input_name);
                const auto raw = read_all((std::filesystem::path(std::string(argv[2])).parent_path() / (input_name + ".rgb565")).string());
                if (raw.size() != 416u * 416u * 2u) throw std::runtime_error("Input size mismatch");
                if (terminal::sha256(raw.data(), raw.size()) != spec["rgb565Sha256"].get<std::string>())
                    throw std::runtime_error("Input hash mismatch for " + input_name);
                input.assign(size_t(channels) * 224 * 224, 0);
                model_input_rows(reinterpret_cast<const uint16_t*>(raw.data()), input.data(), 0, 640, channels);
                reference_output.clear();
                printf("BENCH_INPUT %s %s input_sha=%s\n", phase_name.c_str(), input_name.c_str(),
                       terminal::sha256(input.data(), input.size()).c_str());
                fflush(stdout);

                for (const std::string cond : {"pl", "arm_o0", "arm_novec", "arm_vec"}) {
                    const int warmups = warmup.value(cond, 0);
                    for (int w = 0; w < warmups; ++w) execute(phase_name, input_name, -1, -1, cond, false);
                }

                for (int round = 0; round < rounds; ++round) {
                    if ((now_ns() - run_begin) / 1000000ull > budget_ms) { truncated = true; break; }
                    std::vector<std::string> tasks = arm_conditions;
                    for (int i = 0; i < pl_per_round; ++i) tasks.push_back("pl");
                    std::shuffle(tasks.begin(), tasks.end(), rng);
                    for (size_t t = 0; t < tasks.size(); ++t)
                        execute(phase_name, input_name, round, int(t), tasks[t], true);
                }
                printf("BENCH_INPUT_DONE %s %s\n", phase_name.c_str(), input_name.c_str());
                fflush(stdout);
            }
        }

        json counts_json = json::object();
        for (const auto& kv : counts) counts_json[kv.first] = kv.second;
        meta["counts"] = counts_json;
        meta["truncated"] = truncated;
        meta["cpuFreqKHzEnd"] = read_text("/sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq");
        meta["thermalEnd"] = read_text("/sys/class/thermal/thermal_zone0/temp");
        meta["wallEndNs"] = now_ns();
        std::ofstream meta_out(out_dir + "/run_meta.json");
        meta_out << meta.dump(2);
        meta_out.close();
        printf("BENCH_META %s\n", json{{"counts", counts_json}, {"truncated", truncated}}.dump().c_str());
        fflush(stdout);
        return 0;
    } catch (const std::exception& error) {
        fprintf(stderr, "BENCH_ERROR %s\n", error.what());
        return 1;
    }
}
