#include "core.h"
#include "nlohmann/json.hpp"
#include <fstream>
#include <iostream>
using json=nlohmann::json;
int main(int argc,char** argv) {
    if(argc!=2)return 2;
    std::ifstream stream(argv[1]);json cases;stream>>cases;json results=json::array();
    if(cases.is_object() && cases.contains("tensors")) {
        for(const auto& c:cases["tensors"]) {
            const auto out0=c["out0"].get<std::vector<int8_t>>(),out1=c["out1"].get<std::vector<int8_t>>();
            json boxes=json::array();for(const auto& b:terminal::detect(out0.data(),out1.data()))boxes.push_back({{"classId",b.class_id},{"confidence",b.confidence},{"x1",b.x1},{"y1",b.y1},{"x2",b.x2},{"y2",b.y2}});
            results.push_back(boxes);
        }
        std::cout<<results.dump();return 0;
    }
    for(const auto& c:cases) {
        terminal::Rules rules;rules.classes=c["rules"]["classes"].size();const auto& r=c["rules"]["region"];
        rules.region={r["x"],r["y"],r["width"],r["height"]};rules.confidence=c["acceptance"]["confidence"];rules.quality_gate=c["acceptance"]["qualityGate"];
        for(const auto& check:c["rules"]["checks"])rules.checks.push_back({check["classId"],check["min"],check["max"]});
        std::vector<terminal::Box> boxes;if(!c["detections"].is_null())for(const auto& b:c["detections"])boxes.push_back({b["classId"],b["confidence"],b["x1"],b["y1"],b["x2"],b["y2"]});
        auto decision=terminal::evaluate(rules,boxes,!c["detections"].is_null(),c["quality"]=="PASS",c.value("errorCode",0));
        json row={{"result",terminal::name(decision.result)},{"outsideRegion",decision.outside},{"findings",json::array()}};
        for(const auto& f:decision.findings)row["findings"].push_back({{"classId",f.check.class_id},{"count",f.count},{"uncertain",f.uncertain},{"result",terminal::name(f.result)}});
        results.push_back(row);
    }
    std::cout<<results.dump();
}
