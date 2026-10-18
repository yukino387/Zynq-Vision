#include "core.h"
#include "hardware.h"
#include "nlohmann/json.hpp"
#include "httplib.h"
#include <atomic>
#include <chrono>
#include <csignal>
#include <cctype>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <mutex>
#include <thread>
#include <fcntl.h>
#include <sys/file.h>
#include <sys/statvfs.h>
#include <unistd.h>

namespace fs=std::filesystem;
using json=nlohmann::json;
using namespace terminal;
namespace {
std::atomic<bool> running{true};
uint64_t clock_ns(){return std::chrono::duration_cast<std::chrono::nanoseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();}
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
Rules load_rules(const json& job) {
    const auto& s=job.at("snapshot"),&r=s.at("rules"),&roi=r.at("region");Rules rules;
    rules.classes=r.at("classes").size();rules.region={roi.at("x"),roi.at("y"),roi.at("width"),roi.at("height")};rules.confidence=s.at("acceptance").at("confidence");rules.quality_gate=s.at("acceptance").at("qualityGate");
    for(const auto& c:r.at("checks"))rules.checks.push_back({c.at("classId"),c.at("min"),c.at("max")});
    if(rules.classes<1 || rules.classes>6 || rules.checks.size()!=rules.classes)throw std::runtime_error("Invalid job rules");
    return rules;
}
json decision_json(const Decision& decision,const json& job) {
    json findings=json::array();for(const auto& f:decision.findings)findings.push_back({{"classId",f.check.class_id},{"label",job["snapshot"]["rules"]["classes"][f.check.class_id]},{"min",f.check.minimum},{"max",f.check.maximum},{"count",f.count},{"uncertain",f.uncertain},{"result",name(f.result)}});
    return {{"result",name(decision.result)},{"findings",findings},{"outsideRegion",decision.outside}};
}
struct Record {fs::path path;json payload;std::string request;bool acknowledged=false;bool committed=true;json decision;};
json compact_payload(const json& payload) {
    json compact;for(const auto* key:{"batchId","bootId","sequence","localResult","rawSha256","monotonicNs","frameId"})compact[key]=payload.at(key);return compact;
}
class Engine {
    fs::path root,jobs;
    Hardware hardware;
    std::mutex mutex;
    json job=nullptr,last=nullptr;
    Rules rules;
    Frame frame;
    std::string error,boot_id,sync_error;
    uint32_t sequence=0;
    uint64_t checked_frame=0;
    bool paused=false;
    std::string pending_storage;
    std::map<std::string,Record> records;
public:
    Engine(fs::path root,fs::path jobs):root(std::move(root)),jobs(std::move(jobs)) {
        fs::create_directories(this->root/"records");
        boot_id=read_text("/proc/sys/kernel/random/boot_id",64);while(!boot_id.empty() && std::isspace(boot_id.back()))boot_id.pop_back();
        for(const auto& entry:fs::directory_iterator(this->root/"records"))if(entry.path().extension()==".json") {
            const auto saved=read_record(entry.path());const auto payload=saved.at("payload");
            const std::string request=saved.at("requestId");
            bool acknowledged=false;
            if(fs::exists(entry.path().string()+".ack")){try{const auto receipt=json::parse(read_text(entry.path().string()+".ack"));acknowledged=receipt.at("rawSha256")==payload.at("rawSha256") && receipt.at("id").get<std::string>().find(":"+payload.at("bootId").get<std::string>()+":"+std::to_string(payload.at("sequence").get<unsigned>()))!=std::string::npos;}catch(const std::exception&){}}
            records.emplace(request,Record{entry.path(),compact_payload(payload),request,acknowledged,true,saved.at("decision")});
            if(payload.at("bootId")==boot_id)sequence=std::max(sequence,payload.at("sequence").get<uint32_t>());
        }
        hardware.initialize_camera();
        if(fs::exists(this->root/"active.json")){const auto active=json::parse(read_text(this->root/"active.json"));select(active.at("id"));}
    }
    json available() {
        json list=json::array();if(!fs::exists(jobs))return list;
        for(const auto& entry:fs::directory_iterator(jobs))if(entry.is_directory() && fs::exists(entry.path()/"job.json")) {
            try {auto candidate=json::parse(read_text(entry.path()/"job.json"));if(candidate.at("id")==entry.path().filename().string())list.push_back({{"id",candidate.at("id")},{"name",candidate.at("name")}});}catch(const std::exception&){}
        }
        return list;
    }
    void select(const std::string& id) {
        if(id.empty() || id.size()>80 || id.find_first_not_of("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")!=std::string::npos)throw std::runtime_error("Invalid job identifier");
        const auto path=jobs/id;auto candidate=json::parse(read_text(path/"job.json"));
        if(candidate.at("formatVersion")!=1 || candidate.at("id")!=id)throw std::runtime_error("Job identity mismatch");
        if(fs::exists(root/"connection.json") && json::parse(read_text(root/"connection.json")).at("deviceId")!=candidate.at("deviceId"))throw std::runtime_error("This job belongs to a different terminal");
        const auto manifest=candidate.at("manifest");
        const auto scales=manifest.at("quantization").at("outputScales");
        if(manifest.at("networkTemplate")!="ZYNQ7020_NEU_INT8_V1" || manifest.at("classCount")!=6 || manifest.at("classes").size()!=6 || scales.size()!=2 || std::abs(scales[0].get<double>()-.11581249687615341)>1e-15 || std::abs(scales[1].get<double>()-.15977688286248154)>1e-15)throw std::runtime_error("Unsupported postprocessing profile");
        auto policy=load_rules(candidate);const auto binary=read_text(path/"model.bin",6416360);
        std::vector<uint8_t> weights(binary.begin(),binary.end());
        std::lock_guard<std::mutex> lock(mutex);
        if(!pending_storage.empty())throw std::runtime_error("Resolve the previous storage operation before selecting another job");
        job=nullptr;frame=Frame{};last=nullptr;paused=true;
        try {
            hardware.load_model(weights,candidate["snapshot"].at("modelVersion"),candidate["snapshot"].at("modelPayloadSha256"),candidate.at("modelSha256"));
            durable_write(root/"active.json",json({{"id",id}}).dump());
        }catch(const std::exception& e){error=e.what();throw;}
        job=std::move(candidate);rules=std::move(policy);error.clear();paused=false;
        for(const auto& pair:records){const auto& p=pair.second.payload;if(p.at("batchId")==id && p.at("bootId")==boot_id && (last.is_null() || p.at("sequence").get<unsigned>()>last.at("sequence").get<unsigned>()))last=pair.second.decision;}
    }
    void tick() {
        std::lock_guard<std::mutex> lock(mutex);
        if(job.is_null() || paused || !error.empty())return;
        try {frame=hardware.capture();}catch(const std::exception& e){error=e.what();frame=Frame{};}
    }
    json state() {
        std::lock_guard<std::mutex> lock(mutex);unsigned total=0,pending=0;json counts={{"PASS",0},{"FAIL",0},{"REVIEW",0},{"ERROR",0}};
        for(const auto& pair:records){const auto& record=pair.second;if(!record.committed)continue;if(!record.acknowledged)++pending;if(!job.is_null() && record.payload.at("batchId")==job.at("id")){++total;const std::string value=record.payload.at("localResult");counts[value]=counts[value].get<unsigned>()+1;}}
        return {{"job",job.is_null()?json(nullptr):json({{"id",job.at("id")},{"name",job.at("name")},{"target",job.at("target")},{"instructions",job["snapshot"]["rules"].at("instructions")}})},{"total",total},{"counts",counts},{"pendingSync",pending},{"last",last},{"error",error},{"syncError",sync_error},{"paused",paused},{"frameId",frame.id},{"fresh",frame.monotonic_ns && clock_ns()-frame.monotonic_ns<3000000000ULL}};
    }
    std::string preview() {
        std::lock_guard<std::mutex> lock(mutex);if(frame.pixels.empty())throw std::runtime_error("No current frame");
        json boxes=json::array();for(const auto& b:detect(frame.out0.data(),frame.out1.data()))boxes.push_back({{"classId",b.class_id},{"confidence",b.confidence},{"x1",b.x1},{"y1",b.y1},{"x2",b.x2},{"y2",b.y2}});
        const auto meta=json({{"frameId",frame.id},{"fresh",clock_ns()-frame.monotonic_ns<3000000000ULL},{"boxes",boxes}}).dump();
        const uint32_t size=meta.size();std::string bytes(reinterpret_cast<const char*>(&size),4);bytes+=meta;bytes.append(reinterpret_cast<const char*>(frame.pixels.data()),frame.pixels.size()*2);return bytes;
    }
    json check(const std::string& request) {
        std::lock_guard<std::mutex> lock(mutex);
        const auto found=records.find(request);if(found!=records.end()) {
            auto& record=found->second;
            if(!record.committed) {
                durable_write(record.path,record_envelope(request,record.payload,record.decision).dump());record.committed=true;
                record.payload=compact_payload(record.payload);pending_storage.clear();
            }
            if(!job.is_null() && record.payload.at("batchId")==job.at("id") && (last.is_null() || last.at("sequence").get<unsigned>()<=record.payload.at("sequence").get<unsigned>()))last=record.decision;
            return record.decision;
        }
        if(!pending_storage.empty())throw std::runtime_error("Resolve the previous storage operation before checking another item");
        if(request.size()!=36 || request.find_first_not_of("0123456789abcdef-")!=std::string::npos)throw std::runtime_error("Invalid check request");
        if(job.is_null() || paused || !error.empty())throw std::runtime_error("No active inspection job");
        try {frame=hardware.capture();}catch(const std::exception& e){error=e.what();frame=Frame{};throw;}
        if(!frame.monotonic_ns || clock_ns()-frame.monotonic_ns>3000000000ULL)throw std::runtime_error("No fresh inference frame");
        if(checked_frame==frame.monotonic_ns)throw std::runtime_error("This frame was already checked");
        struct statvfs space{};if(statvfs(root.c_str(),&space) || uint64_t(space.f_bavail)*space.f_frsize<64*1024*1024)throw std::runtime_error("Insufficient evidence storage");
        if(sequence==2147483647)throw std::runtime_error("Check sequence exhausted");
        const auto boxes=detect(frame.out0.data(),frame.out1.data());const auto decision=evaluate(rules,boxes,true,quality(frame.pixels.data()));
        json payload={{"formatVersion",1},{"batchId",job.at("id")},{"bootId",boot_id},{"sequence",++sequence},{"frameId",frame.id},{"monotonicNs",std::to_string(frame.monotonic_ns)},{"capturedAt",nullptr},{"modelPayloadSha256",job["snapshot"].at("modelPayloadSha256")},{"raw",base64(frame.pixels.data(),frame.pixels.size()*2)},{"out0",base64(frame.out0.data(),frame.out0.size())},{"out1",base64(frame.out1.data(),frame.out1.size())},{"rawSha256",sha256(frame.pixels.data(),frame.pixels.size()*2)},{"localResult",name(decision.result)}};
        auto report=decision_json(decision,job);report["sequence"]=sequence;report["saved"]=true;
        const auto path=root/"records"/(boot_id+"-"+std::to_string(sequence)+".json");
        records.emplace(request,Record{path,payload,request,false,false,report});checked_frame=frame.monotonic_ns;
        pending_storage=request;
        durable_write(path,record_envelope(request,payload,report).dump());
        records.at(request).committed=true;records.at(request).payload=compact_payload(payload);pending_storage.clear();
        last=std::move(report);return last;
    }
    void pause(bool value) {std::lock_guard<std::mutex> lock(mutex);paused=value;if(value)frame=Frame{};}
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
                {std::lock_guard<std::mutex> lock(mutex);records.at(key).acknowledged=true;}
            }
            std::lock_guard<std::mutex> lock(mutex);sync_error.clear();
        }catch(const std::exception& e){std::lock_guard<std::mutex> lock(mutex);sync_error=e.what();}
    }
};
}
int main(int argc,char** argv) {
    if(argc!=3){std::cerr<<"Usage: vision-engine STATE_DIRECTORY JOB_DIRECTORY\n";return 2;}
    try {
        fs::create_directories(argv[1]);const int lock_fd=open((fs::path(argv[1])/"engine.lock").c_str(),O_RDWR|O_CREAT|O_CLOEXEC,0600);
        if(lock_fd<0 || flock(lock_fd,LOCK_EX|LOCK_NB))throw std::runtime_error("A terminal engine already owns this state directory");
        Engine engine(argv[1],argv[2]);httplib::Server server;server.new_task_queue=[] { return new httplib::ThreadPool(2); };server.set_payload_max_length(4096);
        auto guard=[](auto action,httplib::Response& response){try{response.set_content(action().dump(),"application/json");}catch(const std::exception& e){response.status=409;response.set_content(json({{"error",e.what()}}).dump(),"application/json");}};
        server.Get("/state",[&](const auto&,auto& r){guard([&]{return engine.state();},r);});
        server.Get("/jobs",[&](const auto&,auto& r){guard([&]{return engine.available();},r);});
        server.Get("/frame",[&](const auto&,auto& r){try{r.set_content(engine.preview(),"application/octet-stream");}catch(const std::exception& e){r.status=409;r.set_content(e.what(),"text/plain");}});
        server.Post("/select",[&](const auto& q,auto& r){guard([&]{engine.select(json::parse(q.body).at("id"));return engine.state();},r);});
        server.Post("/check",[&](const auto& q,auto& r){
            std::string request;
            try {request=json::parse(q.body).at("requestId");r.set_content(engine.check(request).dump(),"application/json");}
            catch(const std::exception& e){r.status=409;r.set_content(json({{"error",e.what()},{"mayHaveSaved",engine.known_request(request)}}).dump(),"application/json");}
        });
        server.Post("/pause",[&](const auto& q,auto& r){guard([&]{engine.pause(json::parse(q.body).at("paused"));return engine.state();},r);});
        std::signal(SIGTERM,[](int){running=false;});std::signal(SIGINT,[](int){running=false;});
        std::thread worker([&]{while(running){engine.tick();std::this_thread::sleep_for(std::chrono::milliseconds(5));}});
        std::thread syncing([&]{while(running){engine.sync();for(unsigned i=0;i<100 && running;++i)std::this_thread::sleep_for(std::chrono::milliseconds(100));}});
        std::thread stopping([&]{while(running)std::this_thread::sleep_for(std::chrono::milliseconds(100));server.stop();});
        const bool listened=server.listen("127.0.0.1",8877);running=false;worker.join();syncing.join();stopping.join();close(lock_fd);return listened?0:1;
    }catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
