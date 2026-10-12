#include "src/top.h"
#include <vector>
#include <cstdint>
#define main original_operator_checks
#include "../operator_pipeline_test/test.cpp"
#undef main
int main() {
    if (!check(32,8,64,3,1,1) || !check(32,8,75,1,1,0,true)
        || !check(32,128,4,3,1,1) || !check(16,256,4,3,1,1)
        || !check(16,512,4,1,1,0,true)) return 2;
    std::vector<data_t> direct(65536,0), scheduled(65536,0), table(560,0);
    for (int i=0;i<256;++i) direct[i]=data_t((i%31-15)/64.0);
    for (int i=0;i<144;++i) direct[50000+i]=data_t((i%13-6)/256.0);
    for (int i=0;i<4;++i) direct[51000+i]=data_t((i-2)/64.0);
    scheduled=direct;
    for (int i=0;i<28;++i) {
        const unsigned input=i ? 1024+(i-1)*1024 : 0, output=1024+i*1024;
        const unsigned op=i==27 ? 2 : (i%2 ? 1 : 3);
        const uint32_t words[10]={input,output,50000,51000,4,4,8,1,op,unsigned(i%2)};
        for (int j=0;j<10;++j) {
            table[20*i+2*j].range(15,0)=words[j]&65535;
            table[20*i+2*j+1].range(15,0)=words[j]>>16;
        }
        data_t* m=direct.data();
        conv(m+input,m+input,m+input,m+input,m+50000,m+50000,m+50000,m+50000,
             m+51000,m+output,m+output,m+output,m+output,4,4,8,1,op,i%2);
    }
    data_t* m=scheduled.data();
    conv(m,m,m,m,m,m,m,m,table.data(),m,m,m,m,28,0,0,0,4,0);
    for (unsigned i=0;i<direct.size();++i)
        if (direct[i].range(15,0)!=scheduled[i].range(15,0)) return 1;
    for (unsigned i=0;i<8192;++i) direct[i]=data_t((i%97-48)/64.0);
    scheduled=direct;
    for (unsigned i=0;i<2;++i) {
        const unsigned input=i ? 32000 : 0, output=i ? 0 : 32000, size=i ? 16 : 8, op=i ? 2 : 0;
        const uint32_t words[10]={input,output,0,0,128,128,size,0,op,0};
        for (unsigned j=0;j<10;++j) {
            table[20*i+2*j].range(15,0)=words[j]&65535;
            table[20*i+2*j+1].range(15,0)=words[j]>>16;
        }
        data_t* d=direct.data();
        conv(d+input,d+input,d+input,d+input,d,d,d,d,d,d+output,d+output,d+output,d+output,128,128,size,0,op,0);
    }
    m=scheduled.data();
    conv(m,m,m,m,m,m,m,m,table.data(),m,m,m,m,2,0,0,0,4,0);
    for (unsigned i=0;i<direct.size();++i)
        if (direct[i].range(15,0)!=scheduled[i].range(15,0)) return 3;
    std::cout<<"PASS: 28 PL-scheduled operators match individual calls; guards unchanged"<<std::endl;
    return 0;
}
