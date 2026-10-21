#include "core.h"
#include "hardware.h"
#include "passage.h"
#include "nlohmann/json.hpp"
#include "httplib.h"
#include <algorithm>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <csignal>
#include <cctype>
#include <cmath>
#include <ctime>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <mutex>
#include <thread>
#include <fcntl.h>
#include <sched.h>
#include <sys/file.h>
#include <sys/statvfs.h>
#include <unistd.h>

namespace fs=std::filesystem;
using json=nlohmann::json;
using namespace terminal;
namespace {
std::atomic<bool> running{true};
std::atomic<bool> sync_requested{false};
uint64_t clock_ns(){return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();}
std::string utc_now() {
    const auto now=std::chrono::system_clock::now();const std::time_t seconds=std::chrono::system_clock::to_time_t(now);
    std::tm utc{};gmtime_r(&seconds,&utc);char text[32]{};std::strftime(text,sizeof(text),"%Y-%m-%dT%H:%M:%SZ",&utc);return text;
}
std::string read_text(const fs::path& path,size_t limit=1024*1024) {
    std::ifstream file(path,std::ios::binary);if(!file)throw std::runtime_error("Cannot read "+path.string());
    file.seekg(0,std::ios::end);const auto size=file.tellg();if(size<0 || uint64_t(size)>limit)throw std::runtime_error("File exceeds limit");
    file.seekg(0);return std::string(std::istreambuf_iterator<char>(file),{});
}
void durable_write(const fs::path& path,const std::string& text) {
    const auto temporary=path.string()+".tmp";
    const int fd=open(temporary.c_str(),O_WRONLY|O_CREAT|O_TRUNC|O_CLOEXEC,0600);if(fd<0)throw std::runtime_error("Cannot create record");
    size_t offset=0;while(offset<text.size()){const auto n=write(fd,text.data()+offset,text.size()-offset);if(n<=0){close(fd);throw std::runtime_error("Record write failed");}offset+=size_t(n);}
    if(fsync(fd)){close(fd);throw std::runtime_error("Record sync failed");}close(fd);
    fs::rename(temporary,path);
    const int directory=open(path.parent_path().c_str(),O_RDONLY|O_DIRECTORY|O_CLOEXEC);if(directory<0)throw std::runtime_error("Cannot sync record directory");
    const int result=fsync(directory);close(directory);if(result)throw std::runtime_error("Record directory sync failed");
}
json record_envelope(const std::string& request,const json& payload,const json& decision) {
    json document={{"formatVersion",1},{"requestId",request},{"payload",payload},{"decision",decision}};
    const auto text=document.dump();document["sha256"]=sha256(text.data(),text.size());return document;
}
json read_record(const fs::path& path) {
    auto document=json::parse(read_text(path));const std::string digest=document.at("sha256");document.erase("sha256");
    const auto text=document.dump();
    if(document.at("formatVersion")!=1 || sha256(text.data(),text.size())!=digest)throw std::runtime_error("Stored evidence checksum mismatch");
    return document;
}
std::string base64(const void* source,size_t size) {
    static const char* digits="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";const auto p=static_cast<const uint8_t*>(source);std::string out;
    out.reserve((size+2)/3*4);for(size_t i=0;i<size;i+=3){const unsigned n=(unsigned(p[i])<<16)|(i+1<size?unsigned(p[i+1])<<8:0)|(i+2<size?p[i+2]:0);out+=digits[(n>>18)&63];out+=digits[(n>>12)&63];out+=i+1<size?digits[(n>>6)&63]:'=';out+=i+2<size?digits[n&63]:'=';}return out;
}
void validate_manifest(const json& manifest) {
    const auto scales=manifest.at("quantization").at("outputScales");
    if(manifest.at("networkTemplate")!="ZYNQ7020_NEU_INT8_V1" || manifest.at("classCount")!=6 || manifest.at("classes").size()!=6 || scales.size()!=2 || std::abs(scales[0].get<double>()-.11581249687615341)>1e-15 || std::abs(scales[1].get<double>()-.15977688286248154)>1e-15)throw std::runtime_error("Unsupported postprocessing profile");
}
Postprocess load_postprocess(const json& rules) {
    Postprocess p;if(!rules.contains("postprocess")){p.algorithm_version=2;return p;}const auto& r=rules.at("postprocess");
    const auto algorithm=r.value("algorithm",std::string("BOX_FILTER_V3"));
    if(algorithm!="BOX_FILTER_V2" && algorithm!="BOX_FILTER_V3")throw std::runtime_error("Unsupported postprocessing policy");
    p.algorithm_version=algorithm=="BOX_FILTER_V3"?3:2;
    p.nms_iou=r.value("nmsIou",p.nms_iou);p.containment=r.value("containment",p.containment);p.min_area=r.value("minArea",p.min_area);p.max_detections=r.value("maxDetections",p.max_detections);
    p.track_iou=r.value("trackIou",p.track_iou);p.track_min_hits=r.value("trackMinHits",p.track_min_hits);p.track_max_misses=r.value("trackMaxMisses",p.track_max_misses);p.track_max_gap_ms=r.value("trackMaxGapMs",p.track_max_gap_ms);
    if(!std::isfinite(p.nms_iou) || p.nms_iou<.05 || p.nms_iou>.95 || !std::isfinite(p.containment) || p.containment<.5 || p.containment>1 || !std::isfinite(p.min_area) || p.min_area<0 || p.min_area>.1 || !std::isfinite(p.track_iou) || p.track_iou<.05 || p.track_iou>.95 || p.max_detections<1 || p.max_detections>300 || p.track_min_hits<1 || p.track_min_hits>10 || p.track_max_misses>30 || p.track_max_gap_ms<100 || p.track_max_gap_ms>5000)throw std::runtime_error("Invalid postprocessing policy");
    return p;
}
json postprocess_json(const Postprocess& p) {
    return {{"algorithm",p.algorithm_version==3?"BOX_FILTER_V3":"BOX_FILTER_V2"},{"nmsIou",p.nms_iou},{"containment",p.containment},{"minArea",p.min_area},{"maxDetections",p.max_detections},{"trackIou",p.track_iou},{"trackMinHits",p.track_min_hits},{"trackMaxMisses",p.track_max_misses},{"trackMaxGapMs",p.track_max_gap_ms}};
}
json filter_json(const FilterResult& r,const Postprocess& p){return {{"policy",postprocess_json(p)},{"candidates",r.candidates},{"invalid",r.invalid},{"tiny",r.tiny},{"nested",r.nested},{"suppressed",r.suppressed},{"overflow",r.overflow}};}
Decision filtered_decision(const Rules& rules,const FilterResult& filtered,const Frame& frame) {
    auto d=evaluate(rules,filtered.boxes,true,quality(frame.pixels.data()));
    if(filtered.overflow || filtered.invalid)d.result=Result::Review;
    return d;
}
Rules load_rules(const json& product) {
    const auto& r=product.at("rules"),&roi=r.at("region");Rules rules;rules.postprocess=load_postprocess(r);
    rules.classes=r.at("classes").size();rules.region={roi.at("x"),roi.at("y"),roi.at("width"),roi.at("height")};rules.confidence=product.at("acceptance").at("confidence");rules.quality_gate=product.at("acceptance").at("qualityGate");
    for(const auto& c:r.at("checks")) {
        Check check{c.at("classId"),c.at("min"),c.at("max")};
        if(c.contains("region")){const auto& area=c.at("region");check.positioned=true;check.region={area.at("x"),area.at("y"),area.at("width"),area.at("height")};}
        rules.checks.push_back(check);
    }
    if(rules.classes<1 || rules.classes>6 || rules.checks.size()!=rules.classes)throw std::runtime_error("Invalid product rules");
    return rules;
}
json decision_json(const Decision& decision,const json& product) {
    json findings=json::array();for(const auto& f:decision.findings)findings.push_back({{"classId",f.check.class_id},{"label",product["rules"]["classes"][f.check.class_id]},{"min",f.check.minimum},{"max",f.check.maximum},{"count",f.count},{"uncertain",f.uncertain},{"result",name(f.result)}});
    return {{"result",name(decision.result)},{"findings",findings},{"outsideRegion",decision.outside}};
}
struct Record {fs::path path;json payload;std::string request;bool acknowledged=false;bool committed=true;json decision;int64_t order=0;};
json compact_payload(const json& payload) {
    json compact;for(const auto* key:{"bootId","sequence","localResult","rawSha256","monotonicNs","frameId","modelId","modelVersion","planId","planName","planVersion","product"})compact[key]=payload.at(key);if(payload.contains("productionRunId"))compact["productionRunId"]=payload["productionRunId"];return compact;
}
class Engine {
    fs::path root;
    Hardware hardware;
    std::mutex hardware_mutex;
    std::mutex mutex;
    std::condition_variable frame_ready;
    uint64_t preview_frame_ns=0;
    std::string preview_bytes;
    json model=nullptr,product=nullptr,last=nullptr;
    Rules rules;
    Frame frame;
    std::vector<Box> frame_boxes;
    FilterResult frame_filter;
    Tracker tracker;
    bool frame_decoded=false;
    std::string error,boot_id,sync_error,production_run;
    uint32_t sequence=0;
    uint64_t checked_frame=0;
    uint64_t captured_frames=0;
    double capture_ms=0,prepare_ms=0,conv_ms=0,forward_ms=0,post_ms=0,extract_ms=0;
    bool paused=true,production=false;
    Passage passage;
    std::string pending_storage;
    std::map<std::string,Record> records;
    std::array<unsigned,4> total_counts{};
    std::array<unsigned,4> run_counts{};
    unsigned pending_count=0;
    void count_record(const Record& record) {
        const std::string result=record.payload.at("localResult");
        const unsigned index=result=="PASS"?0:result=="FAIL"?1:result=="REVIEW"?2:3;
        ++total_counts[index];
        if(!production_run.empty() && record.payload.value("productionRunId",std::string())==production_run)++run_counts[index];
        if(!record.acknowledged)++pending_count;
    }
    static json counts_json(const std::array<unsigned,4>& counts) {return {{"PASS",counts[0]},{"FAIL",counts[1]},{"REVIEW",counts[2]},{"ERROR",counts[3]}};}

    void capture_finished(uint64_t elapsed) {
        capture_ms=double(elapsed)/1000000;++captured_frames;
        prepare_ms=hardware.prepare_ns.load()/1000000.0;conv_ms=hardware.conv_ns.load()/1000000.0;
        forward_ms=hardware.forward_ns.load()/1000000.0;post_ms=hardware.post_ns.load()/1000000.0;extract_ms=hardware.extract_ns.load()/1000000.0;
    }
    Frame capture_frame() {
        const auto before=clock_ns();auto result=hardware.capture();
        capture_finished(clock_ns()-before);return result;
    }
    void clear_product_file() {
        std::error_code ignored;fs::remove(root/"product.json",ignored);
    }
    void reset_runtime() {
        tracker.reset();frame_filter=FilterResult{};frame_boxes.clear();frame_decoded=false;
        frame=Frame{};last=nullptr;production=false;production_run.clear();run_counts={};passage.reset();paused=model.is_null();
        preview_bytes.clear();preview_frame_ns=0;frame_ready.notify_all();
    }
public:
    explicit Engine(fs::path root):root(std::move(root)) {
        fs::create_directories(this->root/"records");
        fs::create_directories(this->root/"model");
        boot_id=read_text("/proc/sys/kernel/random/boot_id",64);while(!boot_id.empty() && std::isspace(boot_id.back()))boot_id.pop_back();
        for(const auto& entry:fs::directory_iterator(this->root/"records"))if(entry.path().extension()==".json") {
            try {
                const auto saved=read_record(entry.path());const auto payload=saved.at("payload");
                if(!payload.contains("modelId"))continue;
                const std::string request=saved.at("requestId");
                bool acknowledged=false;
                if(fs::exists(entry.path().string()+".ack")){try{const auto receipt=json::parse(read_text(entry.path().string()+".ack"));acknowledged=receipt.at("rawSha256")==payload.at("rawSha256") && receipt.at("id").get<std::string>().find(":"+payload.at("bootId").get<std::string>()+":"+std::to_string(payload.at("sequence").get<unsigned>()))!=std::string::npos;}catch(const std::exception&){}}
                const auto inserted=records.emplace(request,Record{entry.path(),compact_payload(payload),request,acknowledged,true,saved.at("decision"),fs::last_write_time(entry.path()).time_since_epoch().count()});
                if(inserted.second)count_record(inserted.first->second);
                if(payload.at("bootId")==boot_id)sequence=std::max(sequence,payload.at("sequence").get<uint32_t>());
            }catch(const std::exception&) {}
        }
        hardware.initialize_camera();
        try {
            if(fs::exists(this->root/"model"/"model.json"))set_model(json::parse(read_text(this->root/"model"/"model.json")));
        }catch(const std::exception& e){error=e.what();model=nullptr;paused=true;}
        try {
            if(fs::exists(this->root/"product.json"))set_product(json::parse(read_text(this->root/"product.json")));
        }catch(const std::exception& e){if(error.empty())error=e.what();product=nullptr;rules=Rules{};clear_product_file();paused=true;}
        if(!model.is_null())paused=product.is_null();
    }
    json state() {
        std::lock_guard<std::mutex> lock(mutex);unsigned total=0;
        const auto counts=counts_json(total_counts);for(const auto& value:counts.items())total+=value.value().get<unsigned>();
        json model_state=nullptr,product_state=nullptr;
        if(!model.is_null())model_state={{"id",model.at("id")},{"version",model.at("version")},{"payloadSha256",model.at("payloadSha256")},{"weightsSha256",model.at("weightsSha256")},{"classes",model.at("classes")}};
        if(!product.is_null()) {
            const auto& r=product.at("rules");json checks=json::array();
            for(const auto& c:r.at("checks")){auto check=c;check["label"]=r.at("classes").at(c.at("classId").get<unsigned>());checks.push_back(check);}
            product_state={{"id",product.at("id")},{"name",product.at("name")},{"version",product.at("version")},{"product",r.at("product")},{"purpose",r.at("purpose")},{"region",r.at("region")},{"instructions",r.at("instructions")},{"checks",checks},{"postprocess",postprocess_json(rules.postprocess)},{"acceptance",product.at("acceptance")}};
        }
        return {{"model",model_state},{"product",product_state},{"total",total},{"counts",counts},{"pendingSync",pending_count},{"last",last},{"error",error},{"syncError",sync_error},{"paused",paused},{"production",production},{"productionRunId",production_run.empty()?json(nullptr):json(production_run)},{"runCounts",counts_json(run_counts)},{"runTotal",run_counts[0]+run_counts[1]+run_counts[2]+run_counts[3]},{"passagePhase",production?passage.phase():"STOPPED"},{"passageSamples",passage.samples()},{"pendingRequestId",pending_storage.empty()?json(nullptr):json(pending_storage)},{"frameId",frame.id},{"fresh",frame.monotonic_ns && clock_ns()-frame.monotonic_ns<3000000000ULL},{"diagnostics",{{"capturedFrames",captured_frames},{"lastCaptureMs",captured_frames?json(capture_ms):json(nullptr)},{"hwPrepareMs",prepare_ms},{"hwConvMs",conv_ms},{"hwForwardMs",forward_ms},{"hwPostMs",post_ms},{"hwExtractMs",extract_ms},{"cameraInitialized",true},{"modelVersion",model.is_null()?json(nullptr):model.at("version")}}}};
    }
    json history(unsigned page,const std::string& filter) {
        std::lock_guard<std::mutex> lock(mutex);std::vector<const Record*> selected;
        for(const auto& pair:records)if(pair.second.committed && (filter.empty() || pair.second.payload.at("localResult")==filter))selected.push_back(&pair.second);
        std::sort(selected.begin(),selected.end(),[](const auto* a,const auto* b){return a->order>b->order;});
        json items=json::array();const size_t first=size_t(page)*20;
        for(size_t i=first;i<selected.size() && i<first+20;++i){const auto& r=*selected[i];auto item=r.payload;item["file"]=r.path.filename().string();item["result"]=r.payload.at("localResult");item["synced"]=r.acknowledged;item["findings"]=r.decision.value("findings",json::array());if(r.acknowledged){try{const auto receipt=json::parse(read_text(r.path.string()+".ack"));item["inspectionId"]=receipt.at("inspectionId");item["platformResult"]=receipt.at("result");}catch(const std::exception&){}}items.push_back(std::move(item));}
        return {{"items",items},{"total",selected.size()},{"page",page}};
    }
    std::string preview(uint32_t after=0) {
        Frame snapshot;json model_state,product_state;std::vector<Box> decoded_boxes;FilterResult filtered;Postprocess policy;bool decoded=false;
        {
            std::unique_lock<std::mutex> lock(mutex);
            if(after && frame.id==after)frame_ready.wait_for(lock,std::chrono::milliseconds(150),[&]{return frame.id!=after || frame.pixels.empty() || paused || !error.empty();});
            if(frame.pixels.empty() || model.is_null())throw std::runtime_error("No current frame");
            const bool fresh=clock_ns()-frame.monotonic_ns<3000000000ULL;
            if(fresh && preview_frame_ns==frame.monotonic_ns && !preview_bytes.empty())return preview_bytes;
            snapshot=frame;model_state=model;product_state=product;decoded=frame_decoded;policy=rules.postprocess;filtered=frame_filter;if(decoded)decoded_boxes=frame_boxes;
        }
        const bool fresh=clock_ns()-snapshot.monotonic_ns<3000000000ULL;
        if(!decoded){filtered=detect_objects(snapshot.out0.data(),snapshot.out1.data(),policy);decoded_boxes=filtered.boxes;}
        json boxes=json::array();for(const auto& b:decoded_boxes)boxes.push_back({{"classId",b.class_id},{"confidence",b.confidence},{"x1",b.x1},{"y1",b.y1},{"x2",b.x2},{"y2",b.y2},{"trackId",b.track_id},{"trackConfirmed",b.track_confirmed}});
        const auto meta=json({{"postprocess",filter_json(filtered,policy)},{"frameId",snapshot.id},{"fresh",fresh},{"boxes",boxes},{"modelId",model_state.at("id")},{"modelVersion",model_state.at("version")},{"modelPayloadSha256",model_state.at("payloadSha256")},{"modelClasses",model_state.at("classes")},{"planId",product_state.is_null()?json(nullptr):product_state.at("id")},{"planVersion",product_state.is_null()?json(nullptr):product_state.at("version")}}).dump();
        const uint32_t size=meta.size();std::string bytes(reinterpret_cast<const char*>(&size),4);bytes+=meta;bytes.append(reinterpret_cast<const char*>(snapshot.pixels.data()),snapshot.pixels.size()*2);
        std::lock_guard<std::mutex> lock(mutex);
        if(frame.pixels.empty() || paused || !error.empty() || model.is_null() || frame.monotonic_ns!=snapshot.monotonic_ns)throw std::runtime_error("No current frame");
        if(frame.monotonic_ns==snapshot.monotonic_ns){preview_bytes=bytes;preview_frame_ns=snapshot.monotonic_ns;}
        return bytes;
    }
    bool set_model(const json& descriptor) {
        std::lock_guard<std::mutex> hardware_lock(hardware_mutex);
        std::lock_guard<std::mutex> lock(mutex);
        if(production)throw std::runtime_error("请先停止自动检测，再切换模型");
        if(!pending_storage.empty())throw std::runtime_error("请先核对未确认保存的记录");
        if(descriptor.at("formatVersion")!=1)throw std::runtime_error("Invalid model descriptor");
        const auto manifest=descriptor.at("manifest");validate_manifest(manifest);
        const auto binary=read_text(root/"model"/"model.bin",6416360);std::vector<uint8_t> weights(binary.begin(),binary.end());
        if(sha256(weights.data(),weights.size())!=descriptor.at("weightsSha256").get<std::string>())throw std::runtime_error("Model file checksum mismatch");
        hardware.load_model(weights,descriptor.at("version"),descriptor.at("payloadSha256"),descriptor.at("weightsSha256"));
        durable_write(root/"model"/"model.json",descriptor.dump());
        model=descriptor;reset_runtime();
        bool cleared=false;
        if(!product.is_null() && !product_classes_match(product.at("rules").at("classes").get<std::vector<std::string>>(),model.at("classes").get<std::vector<std::string>>())) {
            product=nullptr;rules=Rules{};clear_product_file();paused=true;cleared=true;
        }
        if(!cleared)paused=false;
        return cleared;
    }
    void set_product(const json& descriptor) {
        std::lock_guard<std::mutex> lock(mutex);
        if(production)throw std::runtime_error("请先停止自动检测，再切换产品");
        if(model.is_null())throw std::runtime_error("请先下发模型");
        if(!product_classes_match(descriptor.at("rules").at("classes").get<std::vector<std::string>>(),model.at("classes").get<std::vector<std::string>>()))throw std::runtime_error("产品类别及顺序必须与当前模型一致");
        auto next=load_rules(descriptor);
        if(std::none_of(next.checks.begin(),next.checks.end(),[](const Check& check){return check.minimum>0;}))throw std::runtime_error("自动过件需要至少一个必需类别；请将产品主体加入识别类别");
        durable_write(root/"product.json",descriptor.dump());
        product=descriptor;rules=std::move(next);reset_runtime();paused=false;
    }
    void clear_product() {
        std::lock_guard<std::mutex> lock(mutex);
        if(production)stop_production();
        product=nullptr;rules=Rules{};clear_product_file();reset_runtime();paused=true;
    }
    void set_production(bool enabled) {
        std::lock_guard<std::mutex> hardware_lock(hardware_mutex);
        std::lock_guard<std::mutex> lock(mutex);
        if(enabled) {
            if(production)return;
            if(model.is_null() || product.is_null() || !error.empty() || !pending_storage.empty())throw std::runtime_error("请先在平台部署模型并分配产品");
            if(paused || !frame.monotonic_ns || clock_ns()-frame.monotonic_ns>=3000000000ULL)throw std::runtime_error("等待有效图像后再开始自动检测");
            if(std::none_of(rules.checks.begin(),rules.checks.end(),[](const Check& check){return check.minimum>0;}))throw std::runtime_error("视觉计件需要至少一个必需目标；请将产品主体加入识别类别");
            production_run=read_text("/proc/sys/kernel/random/uuid",64);while(!production_run.empty() && std::isspace(production_run.back()))production_run.pop_back();
            passage.reset();run_counts={};paused=false;production=true;
        } else stop_production();
    }
    void pause(bool value) {std::lock_guard<std::mutex> lock(mutex);if(value)stop_production();paused=value;if(value)frame=Frame{};frame_ready.notify_all();}
    bool known_request(const std::string& request) {std::lock_guard<std::mutex> lock(mutex);return records.count(request)!=0;}
    void sync() {
        if(!fs::exists(root/"connection.json"))return;
        try {
            const auto connection=json::parse(read_text(root/"connection.json"));
            const std::string server=connection.at("server"),token=connection.at("token");
            httplib::Client client(server);client.set_connection_timeout(3,0);client.set_read_timeout(10,0);client.set_write_timeout(10,0);client.set_bearer_token_auth(token);
            std::vector<std::string> pending;{std::lock_guard<std::mutex> lock(mutex);for(const auto& p:records)if(p.second.committed && !p.second.acknowledged)pending.push_back(p.first);}
            for(const auto& key:pending) {
                Record record;{std::lock_guard<std::mutex> lock(mutex);record=records.at(key);}
                const auto saved=read_record(record.path);const auto payload=saved.at("payload");const auto serialized=payload.dump();
                const auto reply=client.Post("/api/terminal/records",serialized,"application/json");
                if(!reply || reply->status!=201)throw std::runtime_error(reply?"Server rejected offline record (HTTP "+std::to_string(reply->status)+")":"Server is unreachable");
                const auto receipt=json::parse(reply->body);const auto expected="terminal:"+connection.at("deviceId").get<std::string>()+":"+record.payload.at("bootId").get<std::string>()+":"+std::to_string(record.payload.at("sequence").get<unsigned>());
                if(receipt.at("id")!=expected || receipt.at("rawSha256")!=record.payload.at("rawSha256"))throw std::runtime_error("Offline acknowledgement mismatch");
                durable_write(record.path.string()+".ack",receipt.dump());
                {std::lock_guard<std::mutex> lock(mutex);if(!records.at(key).acknowledged){records.at(key).acknowledged=true;--pending_count;}}
            }
            std::lock_guard<std::mutex> lock(mutex);sync_error.clear();
        }catch(const std::exception& e){std::lock_guard<std::mutex> lock(mutex);sync_error=e.what();}
    }
    bool tick() {
        std::lock_guard<std::mutex> hardware_lock(hardware_mutex);
        {std::lock_guard<std::mutex> lock(mutex);if(model.is_null() || paused || !error.empty())return false;}
        const auto before=clock_ns();
        try {
            auto next=hardware.capture();
            const auto elapsed=clock_ns()-before;
            std::lock_guard<std::mutex> lock(mutex);
            capture_finished(elapsed);
            if(!paused && !model.is_null() && error.empty()){
                frame=std::move(next);frame_filter=detect_objects(frame.out0.data(),frame.out1.data(),rules.postprocess);frame_boxes=frame_filter.boxes;
                tracker.update(frame_boxes,frame.monotonic_ns,rules.postprocess,frame.pixels.data(),rules.confidence);frame_decoded=true;
                if(production && !product.is_null()) {
                    const auto decision=filtered_decision(rules,frame_filter,frame);
                    if(passage.observe(frame,frame_boxes,rules,decision))save_passage();
                }
                frame_ready.notify_all();
            }
        }catch(const std::exception& e){
            std::lock_guard<std::mutex> lock(mutex);error=e.what();
            try{stop_production();}catch(const std::exception& storage){error+="; "+std::string(storage.what());}
            production=false;paused=true;frame=Frame{};frame_ready.notify_all();return false;
        }
        return true;
    }
    json check(const std::string& request) {
        std::lock_guard<std::mutex> hardware_lock(hardware_mutex);
        std::lock_guard<std::mutex> lock(mutex);
        const auto found=records.find(request);if(found!=records.end()) {
            auto& record=found->second;
            if(!record.committed) {
                durable_write(record.path,record_envelope(request,record.payload,record.decision).dump());record.committed=true;count_record(record);record.order=fs::file_time_type::clock::now().time_since_epoch().count();
                record.payload=compact_payload(record.payload);pending_storage.clear();
            }
            if(last.is_null() || last.at("sequence").get<unsigned>()<=record.payload.at("sequence").get<unsigned>())last=record.decision;
            return record.decision;
        }
        if(production)throw std::runtime_error("自动生产中不能手动记件；请先停止生产");
        if(!pending_storage.empty())throw std::runtime_error("Resolve the previous storage operation before checking another item");
        if(request.size()!=36 || request.find_first_not_of("0123456789abcdef-")!=std::string::npos)throw std::runtime_error("Invalid check request");
        if(model.is_null() || product.is_null() || paused || !error.empty())throw std::runtime_error("No active model and product");
        try {frame=capture_frame();frame_ready.notify_all();}catch(const std::exception& e){error=e.what();frame=Frame{};frame_ready.notify_all();throw;}
        frame_filter=detect_objects(frame.out0.data(),frame.out1.data(),rules.postprocess);frame_boxes=frame_filter.boxes;
        tracker.update(frame_boxes,frame.monotonic_ns,rules.postprocess,frame.pixels.data(),rules.confidence);frame_decoded=true;
        return save_evidence(request,frame,filtered_decision(rules,frame_filter,frame));
    }
private:
    json save_evidence(const std::string& request,const Frame& frame,const Decision& decision,const Passage* source=nullptr) {
        if(!frame.monotonic_ns || frame.pixels.size()!=416*416)throw std::runtime_error("No valid evidence frame");
        if(checked_frame==frame.monotonic_ns)throw std::runtime_error("This frame was already checked");
        struct statvfs space{};if(statvfs(root.c_str(),&space) || uint64_t(space.f_bavail)*space.f_frsize<64*1024*1024)throw std::runtime_error("Insufficient evidence storage");
        if(sequence==2147483647)throw std::runtime_error("Check sequence exhausted");
        json payload={{"postprocess",postprocess_json(rules.postprocess)},{"formatVersion",1},{"planId",product.at("id")},{"planVersion",product.at("version")},{"planName",product.at("name")},{"product",product.at("rules").at("product")},{"modelId",model.at("id")},{"modelVersion",model.at("version")},{"modelPayloadSha256",model.at("payloadSha256")},{"acceptance",product.at("acceptance")},{"bootId",boot_id},{"sequence",++sequence},{"frameId",frame.id},{"monotonicNs",std::to_string(frame.monotonic_ns)},{"capturedAt",utc_now()},{"raw",base64(frame.pixels.data(),frame.pixels.size()*2)},{"out0",base64(frame.out0.data(),frame.out0.size())},{"out1",base64(frame.out1.data(),frame.out1.size())},{"rawSha256",sha256(frame.pixels.data(),frame.pixels.size()*2)},{"localResult",name(decision.result)}};
        if(source) {
            json counts=json::array();for(const auto& f:decision.findings)counts.push_back({{"classId",f.check.class_id},{"count",f.count},{"uncertain",f.uncertain}});
            payload["passage"]={{"samples",source->samples()},{"votes",source->votes()},{"interrupted",source->interrupted()},
                {"consensus",{{"algorithm","COUNT_VECTOR_V1"},{"mode",source->defect()?"PERSISTENT_DEFECT":"COUNT_VECTOR"},{"support",source->support()},{"consecutive",source->consecutive()},{"durationMs",source->span_ms()},{"patterns",source->patterns()},{"unstable",source->unstable()},{"counts",counts}}}};
        }
        if(source)payload["productionRunId"]=production_run;
        auto report=decision_json(decision,product);report["sequence"]=sequence;report["bootId"]=boot_id;report["productionRunId"]=source?json(production_run):json(nullptr);
        const auto filtered=detect_objects(frame.out0.data(),frame.out1.data(),rules.postprocess);
        if(filtered.overflow || filtered.invalid)report["reason"]="目标过多或候选数据异常，请人工复核";
        else if(source && decision.result==Result::Review)report["reason"]="多帧数量不一致、证据不足或检测中断，请人工复核";
        const auto path=root/"records"/(boot_id+"-"+std::to_string(sequence)+".json");
        records.emplace(request,Record{path,payload,request,false,false,report});checked_frame=frame.monotonic_ns;
        pending_storage=request;
        durable_write(path,record_envelope(request,payload,report).dump());
        records.at(request).committed=true;count_record(records.at(request));records.at(request).order=fs::file_time_type::clock::now().time_since_epoch().count();records.at(request).payload=compact_payload(payload);pending_storage.clear();
        last=std::move(report);return last;
    }
    void save_passage() {
        if(!pending_storage.empty())throw std::runtime_error("请先核对未确认保存的记录");
        auto request=read_text("/proc/sys/kernel/random/uuid",64);
        while(!request.empty() && std::isspace(request.back()))request.pop_back();
        save_evidence(request,passage.evidence(),passage.decision(),&passage);
        passage.committed();sync_requested=true;
    }
    void stop_production() {
        if(!production)return;
        production=false;
        passage.finish(true);
        if(passage.ready())save_passage();
        passage.reset();
    }
};
}
int main(int argc,char** argv) {
    if(argc<2 || argc>3){std::cerr<<"Usage: vision-engine STATE_DIRECTORY [JOB_DIRECTORY]\n";return 2;}
    try {
        cpu_set_t service_cpu;CPU_ZERO(&service_cpu);CPU_SET(0,&service_cpu);
        if(sched_setaffinity(0,sizeof(service_cpu),&service_cpu))throw std::runtime_error("Cannot assign service CPU");
        fs::create_directories(argv[1]);const int lock_fd=open((fs::path(argv[1])/"engine.lock").c_str(),O_RDWR|O_CREAT|O_CLOEXEC,0600);
        if(lock_fd<0 || flock(lock_fd,LOCK_EX|LOCK_NB))throw std::runtime_error("A terminal engine already owns this state directory");
        Engine engine(argv[1]);httplib::Server server;server.new_task_queue=[] { return new httplib::ThreadPool(2); };server.set_payload_max_length(1024*1024);
        auto guard=[](auto action,httplib::Response& response){try{response.set_content(action().dump(),"application/json");}catch(const std::exception& e){response.status=409;response.set_content(json({{"error",e.what()}}).dump(),"application/json");}};
        server.Get("/state",[&](const auto&,auto& r){guard([&]{return engine.state();},r);});
        server.Get("/records",[&](const auto& q,auto& r){guard([&]{const auto page=q.has_param("page")?q.get_param_value("page"):"0";if(page.empty() || page.size()>7 || page.find_first_not_of("0123456789")!=std::string::npos)throw std::runtime_error("Invalid page");return engine.history(std::stoul(page),q.has_param("result")?q.get_param_value("result"):"");},r);});
        server.Get("/frame",[&](const auto& q,auto& r){try{
            uint32_t after=0;
            if(q.has_param("after")){const auto value=q.get_param_value("after");if(value.empty() || value.size()>10 || value.find_first_not_of("0123456789")!=std::string::npos || std::stoull(value)>0xffffffffULL)throw std::runtime_error("Invalid frame identifier");after=uint32_t(std::stoull(value));}
            r.set_content(engine.preview(after),"application/octet-stream");
        }catch(const std::exception& e){r.status=409;r.set_content(e.what(),"text/plain");}});
        server.Post("/model",[&](const auto& q,auto& r){
            try{const bool cleared=engine.set_model(json::parse(q.body));auto state=engine.state();state["productCleared"]=cleared;r.set_content(state.dump(),"application/json");}
            catch(const std::exception& e){r.status=409;r.set_content(json({{"error",e.what()}}).dump(),"application/json");}});
        server.Post("/product",[&](const auto& q,auto& r){
            try{const auto body=json::parse(q.body);if(body.value("clear",false))engine.clear_product();else engine.set_product(body);r.set_content(engine.state().dump(),"application/json");}
            catch(const std::exception& e){r.status=409;r.set_content(json({{"error",e.what()}}).dump(),"application/json");}});
        server.Post("/check",[&](const auto& q,auto& r){
            std::string request;
            try {request=json::parse(q.body).at("requestId");r.set_content(engine.check(request).dump(),"application/json");}
            catch(const std::exception& e){r.status=409;r.set_content(json({{"error",e.what()},{"mayHaveSaved",engine.known_request(request)}}).dump(),"application/json");}
        });
        server.Post("/production",[&](const auto& q,auto& r){guard([&]{engine.set_production(json::parse(q.body).at("enabled"));return engine.state();},r);});
        server.Post("/pause",[&](const auto& q,auto& r){guard([&]{engine.pause(json::parse(q.body).at("paused"));return engine.state();},r);});
        server.Post("/sync",[&](const auto&,auto& r){sync_requested=true;r.set_content("{\"queued\":true}","application/json");});
        std::signal(SIGTERM,[](int){running=false;});std::signal(SIGINT,[](int){running=false;});
        std::thread worker([&]{
            cpu_set_t inference_cpu;CPU_ZERO(&inference_cpu);CPU_SET(1,&inference_cpu);
            if(sched_setaffinity(0,sizeof(inference_cpu),&inference_cpu)){std::cerr<<"Cannot assign inference CPU\n";running=false;return;}
            while(running){const bool captured=engine.tick();std::this_thread::sleep_for(std::chrono::microseconds(captured?100:1000));}
            try{engine.set_production(false);}catch(const std::exception& e){std::cerr<<e.what()<<'\n';}
        });
        std::thread syncing([&]{while(running){engine.sync();for(unsigned i=0;i<100 && running;++i){if(sync_requested.exchange(false))break;std::this_thread::sleep_for(std::chrono::milliseconds(100));}}});
        std::thread stopping([&]{while(running)std::this_thread::sleep_for(std::chrono::milliseconds(100));server.stop();});
        const bool listened=server.listen("127.0.0.1",8877);running=false;worker.join();syncing.join();stopping.join();close(lock_fd);return listened?0:1;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
