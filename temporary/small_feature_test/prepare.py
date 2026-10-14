import shutil
from pathlib import Path

test = Path(__file__).resolve().parent
root = test.parents[1]
source = test / 'build/candidate_src'
source.mkdir(parents=True, exist_ok=True)
for path in (root / 'temporary/conv_pipeline_test/build/candidate_src').iterdir():
    if path.suffix in ('.cpp', '.h'):
        shutil.copy2(path, source / path.name)
path = source / 'std_conv.cpp'
code = path.read_text(encoding='utf-8')
needle = '    const unsigned padding=kernel==3?1:0;'
assert code.count(needle) == 1
code = code.replace(needle, '''    if(size==7 && stride==1) {
        uint64_t packed[7];
#pragma HLS ARRAY_PARTITION variable=packed complete
        const unsigned channel=n+Lane;
        if(channel<channels) {
            const unsigned base=channel_base(channel,7)>>3;
            for(unsigned i=0;i<7;++i) {
#pragma HLS PIPELINE II=1
                packed[i]=input[base+i];
            }
        }
        const unsigned padding=kernel==3?1:0;
        const unsigned side=7+2*padding;
        for(unsigned y=0;y<side;++y) for(unsigned x=0;x<side;++x) {
#pragma HLS PIPELINE II=1
            const int sy=int(y)-int(padding),sx=int(x)-int(padding);
            plane[y][x]=channel<channels && sy>=0 && sy<7 && sx>=0 && sx<7
                ?data_t(packed[sy]>>(unsigned(sx)*8)):data_t(0);
        }
        return;
    }
''' + needle)
start = code.index('template<unsigned Lane>\nstatic void load_weight_lane(')
end = code.index('static void load_weight(', start)
parallel = '''template<unsigned Lane>
static void load_weight_lane(data_t bank[Tm/4][Tn][K][K],const uint64_t* weights,
                             unsigned n,unsigned kernel) {
#pragma HLS INLINE off
#pragma HLS ARRAY_PARTITION variable=weight_cache complete dim=1
#pragma HLS ARRAY_PARTITION variable=weight_cache complete dim=2
#pragma HLS BIND_STORAGE variable=weight_cache type=ram_s2p impl=bram
#pragma HLS DEPENDENCE variable=weight_cache inter false
    const unsigned elements=kernel==1?1:9;
    const unsigned words_per_group=kernel==1?1:9;
    uint64_t packed[Tm/4][9];
#pragma HLS ARRAY_PARTITION variable=packed complete dim=1
#pragma HLS BIND_STORAGE variable=packed type=ram_1p impl=lutram
    if(!cache_enabled || !cache_reuse) {
        const unsigned block=(n>>3)*4+Lane;
        const unsigned base=kernel==1?((block<<3)+(block<<2)):((block<<6)+(block<<5)+(block<<3)+(block<<2));
        unsigned group=0,word=0;
        for(unsigned i=0;i<(Tm/4)*words_per_group;++i) {
#pragma HLS PIPELINE II=1
            packed[group][word]=weights[base+i];
            ++word;
            if(word==words_per_group) {word=0;++group;}
        }
    }
    for(unsigned k=0;k<Tn*elements;++k) {
#pragma HLS PIPELINE II=1
        const unsigned cache_offset=kernel==1?n+k:((n<<3)+n+k);
        const unsigned nn=kernel==1?k:k/9;
        const unsigned ky=kernel==1?0:(k%9)/3;
        const unsigned kx=kernel==1?0:k%3;
        for(unsigned group=0;group<Tm/4;++group) {
#pragma HLS UNROLL
            const data_t value=cache_enabled && cache_reuse?weight_cache[Lane][group][cache_offset]
                :data_t(packed[group][k>>3]>>((k&7)*8));
            if(cache_enabled && !cache_reuse)weight_cache[Lane][group][cache_offset]=value;
            bank[group][nn][ky][kx]=value;
        }
    }
}

'''
code = code[:start] + parallel + code[end:]
path.write_bytes(code.encode('utf-8'))
print(source)
