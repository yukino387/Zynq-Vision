from pathlib import Path
import json,re,xml.etree.ElementTree as E

test=Path(__file__).resolve().parent
root=test.parents[1]
build=test/'build'
report=build/'candidate/hls/syn/report/conv_csynth.xml'
tree=E.parse(report)
resources=tree.find('.//AreaEstimates/Resources')
area={k:int(resources.findtext(k)) for k in ['LUT','FF','DSP','BRAM_18K']}
baseline=E.parse(root/'temporary/micro_io_test/build/d/hls/syn/report/conv_csynth.xml').find('.//AreaEstimates/Resources')
baseline_area={k:int(baseline.findtext(k)) for k in area}
assert area['DSP']<=220 and area['BRAM_18K']<=280,area
log=(build/'hls.log').read_text(errors='replace')
non_ii1=[line for line in log.splitlines() if re.search(r'Final II = (?!1\b)\d+',line)]
assert not non_ii1,non_ii1
csim=(build/'csim.log').read_text()
assert 'CSim done with 0 errors.' in csim and 'PASS PS scheduled aligned W8A8 network' in csim
rows={}
for version in ['baseline','candidate']:
    text=(build/f'rtl_{version}/simulation.log').read_text()
    assert 'INPUT RTL PASS' in text
    rows[version]={int(i):dict(cycles=int(c),requests=int(r),writes=int(w)) for i,c,r,w in
        re.findall(r'^INPUT (\d+) (\d+) (\d+) (\d+)',text,re.M)}
cases=json.loads((build/'rtl_baseline/cases.json').read_text())
comparisons=[dict(case=c,baseline=rows['baseline'][i],candidate=rows['candidate'][i]) for i,c in enumerate(cases)]
assert all(r['candidate']['writes']==r['baseline']['writes'] for r in comparisons)
result=dict(baseline='de2d083',hls_estimate=area,baseline_hls_estimate=baseline_area,
            non_ii1=non_ii1,full_network_csim_pass=True,input_rtl_comparisons=comparisons,
            board_test_performed=False)
(build/'results.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(hls_estimate=area,baseline_hls_estimate=baseline_area,full_network_csim_pass=True,
    representative=[comparisons[i] for i in [0,4,7,8,9,10]]),indent=2))
