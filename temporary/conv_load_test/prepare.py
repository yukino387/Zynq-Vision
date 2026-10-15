import subprocess
from pathlib import Path

test = Path(__file__).resolve().parent
root = test.parents[1]
source = test / 'build/candidate_src'
source.mkdir(parents=True, exist_ok=True)
for path in (root / 'hardware/hls/src').iterdir():
    if path.suffix in ('.cpp', '.h'):
        raw = subprocess.check_output(['git', 'show', f'fecf226:hardware/hls/src/{path.name}'], cwd=root)
        (source / path.name).write_bytes(raw)
path = source / 'std_conv.cpp'
code = path.read_text(encoding='utf-8')
start = code.index('template<unsigned Lane>\nstatic void load_weight_lane(')
end = code.index('static void load_weight(', start)
parallel = '''template<unsigned Lane>
static void load_weight_lane(data_t bank[Tm/4][Tn][K][K],const uint64_t* weights,
                             unsigned n,unsigned kernel) {
#pragma HLS INLINE off
#pragma HLS ARRAY_PARTITION variable=weight_cache complete dim=1
#pragma HLS ARRAY_PARTITION variable=weight_cache cyclic factor=2 dim=2
#pragma HLS BIND_STORAGE variable=weight_cache type=ram_s2p impl=bram
#pragma HLS DEPENDENCE variable=weight_cache inter false
    const unsigned elements=kernel==1?1:9;
    const unsigned words_per_group=kernel==1?1:9;
    uint64_t values[2][(Tm/8)*K*K];
#pragma HLS ARRAY_PARTITION variable=values complete dim=1
#pragma HLS BIND_STORAGE variable=values type=ram_1p impl=bram
    if(!cache_enabled || !cache_reuse) {
        const unsigned block=(n>>3)*4+Lane;
        const unsigned base=kernel==1?((block<<3)+(block<<2)):((block<<6)+(block<<5)+(block<<3)+(block<<2));
        unsigned group=0,word=0;
        for(unsigned i=0;i<(Tm/4)*words_per_group;++i) {
#pragma HLS PIPELINE II=1
            const uint64_t packed=weights[base+i];
            const unsigned batch=group>>1;
            const unsigned slot=(kernel==1?batch:(batch<<3)+batch)+word;
            values[group&1][slot]=packed;
            ++word;
            if(word==words_per_group) {word=0;++group;}
        }
    }
    for(unsigned batch=0;batch<Tm/8;++batch) {
        ap_uint<4> nn=0;
        ap_uint<2> ky=0,kx=0;
        for(unsigned k=0;k<Tn*elements;++k) {
#pragma HLS PIPELINE II=1
        const unsigned cache_offset=kernel==1?n+k:((n<<3)+n+k);
        const unsigned slot=(kernel==1?batch:(batch<<3)+batch)+(k>>3);
        for(unsigned parallel=0;parallel<2;++parallel) {
#pragma HLS UNROLL
            const unsigned group=(batch<<1)+parallel;
            const data_t value=cache_enabled && cache_reuse?weight_cache[Lane][group][cache_offset]
                :data_t(values[parallel][slot]>>((k&7)*8));
            if(cache_enabled && !cache_reuse)weight_cache[Lane][group][cache_offset]=value;
            bank[group][nn][ky][kx]=value;
        }
        if(kernel==1) ++nn;
        else if(kx==2) {
            kx=0;
            if(ky==2) {ky=0;++nn;} else ++ky;
        } else ++kx;
        }
    }
}

'''
code = code[:start] + parallel + code[end:]
old = '''    cache_enabled=kernel==1 || ch_in<=128;
    const unsigned out_size=stride==2 ? unsigned(fm_size)>>1 : unsigned(fm_size);'''
new = '''    const unsigned out_size=stride==2 ? unsigned(fm_size)>>1 : unsigned(fm_size);
    cache_enabled=out_size>14 && (kernel==1 || ch_in<=128);'''
assert code.count(old) == 1
code = code.replace(old, new)
path.write_bytes(code.encode('utf-8'))
print(source)
