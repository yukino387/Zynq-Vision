#include <cstdint>
#include <cstring>
#include <cstdio>
#include <vector>
#include <algorithm>
#include <random>
#include <stdexcept>
using data_t=int8_t;
#define Tn 8
#define TRin 29
#define TCin 33
static unsigned size_level(unsigned s) {return s==7?0:s==14?1:s==28?2:s==56?3:s==112?4:5;}
static unsigned plane_size(unsigned s) {return s*(8u<<size_level(s));}
static unsigned channel_base(unsigned c,unsigned s) {return c*plane_size(s);}
#include "build/input_loader.inc"

int main() {
    std::mt19937 rng(7020);
    unsigned cases=0;
    for(unsigned size:{7,14,28,56,112,224}) for(unsigned stride:{1,2}) {
        const unsigned out=size/stride;
        if(out!=7 && out%14) continue;
        const unsigned rows=out==7?7:14,pitch=plane_size(size)/size;
        for(unsigned ci:{1,3,4,5,7,8,9,12,13,16,17}) {
            std::vector<uint64_t> memory[4];
            for(auto& port:memory) {
                port.resize((ci*plane_size(size)+64)/8);
                auto* bytes=reinterpret_cast<int8_t*>(port.data());
                for(unsigned i=0;i<port.size()*8;++i) bytes[i]=int8_t(rng());
            }
            for(unsigned kernel:{1,3}) for(unsigned row:{0u,rows,out-rows}) for(unsigned col:{0u,16u,((out-1)/16)*16}) {
                if(row>=out || col>=out) continue;
                for(unsigned n=0;n<=ci+7;n+=8) {
                    data_t tile[Tn][TRin][TCin];
                    std::memset(tile,0x55,sizeof(tile));
                    load_input(tile,memory[0].data(),memory[1].data(),memory[2].data(),memory[3].data(),n,row,col,size,stride,kernel,ci);
                    const unsigned height=(rows-1)*stride+kernel;
                    const unsigned width=(std::min(16u,out-col)-1)*stride+kernel;
                    for(unsigned lane=0;lane<8;++lane) for(unsigned y=0;y<TRin;++y) for(unsigned x=0;x<TCin;++x) {
                        int8_t expected=0x55;
                        if(n<ci && y<height && x<width) {
                            const int sy=int(row*stride+y)-(kernel==3),sx=int(col*stride+x)-(kernel==3);
                            expected=0;
                            if(n+lane<ci && sy>=0 && sy<int(size) && sx>=0 && sx<int(size)) {
                                const auto* bytes=reinterpret_cast<const int8_t*>(memory[lane%4].data());
                                expected=bytes[(n+lane)*size*pitch+sy*pitch+sx];
                            }
                        }
                        if(tile[lane][y][x]!=expected) {
                            std::printf("FAIL size=%u stride=%u kernel=%u ci=%u n=%u row=%u col=%u lane=%u y=%u x=%u\n",size,stride,kernel,ci,n,row,col,lane,y,x);
                            return 1;
                        }
                    }
                    ++cases;
                }
            }
        }
    }
    std::printf("PASS %u input-tile cases: signed data, distinct ports, channel tails, padding and untouched cells\n",cases);
}
