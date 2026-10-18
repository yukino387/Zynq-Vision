from pathlib import Path
import hashlib,json,re

task=Path(__file__).resolve().parent
repository=task.parents[1]
console=(task/'uart.log').read_text(encoding='utf-8',errors='replace')
def result(marker):
    matches=re.findall(r'^'+re.escape(marker)+r' (\{[^\r\n]+\})',console,re.M)
    assert matches,marker
    return json.loads(matches[-1])
for name in ('panel-build-final','panel-reset-final','program','rootfs'):
    assert (task/(name+'.exit')).read_text().strip()=='0',name
assert (task/'rebuild.done').read_text().strip()=='PASS'
build=json.loads((task/'build-summary.json').read_text(encoding='utf-8-sig'))
assert build['timing']['numeric_timing_pass'] and build['bus_skew']['summary_pass']
stream=result('HDMI_STREAM_TEST_PASSED')
assert all(stream[key]['delta']==0 for key in ('idle','inference','settled'))
with (repository/'hardware/camera/build/terminal/system_wrapper.bit').open('rb') as source:
    bit_sha=hashlib.file_digest(source,'sha256').hexdigest()
document={'date':'2026-10-18','problem':'Monitor displayed only the top strip while both framebuffer pages contained the full interface',
    'baselineStreamErrors':{'before':68043,'after':68163,'seconds':2,'delta':120},
    'changes':['64-beat VDMA read bursts','64-bit custom crossbar with display read priority and no extra data FIFOs',
               'Clear stale preview/results and initialize the empty job selector'],
    'bitstreamSha256':bit_sha,'timing':build['timing']['metrics'],'resources':build['utilization']['resources'],
    'busSkewMinimumSlackNs':build['bus_skew']['minimum_slack_ns'],
    'physicalStreamTest':stream,'physicalCameraInferenceSmoke':result('BOARD_SMOKE_PASSED'),
    'armPanelRegressionPassed':True,'physicalMonitorPictureConfirmed':False,
    'loadMethod':'JTAG PL update with Linux still running from RAM; physical SD/QSPI untouched',
    'pending':['Monitor picture confirmation','Physical keyboard/mouse, deferred by user','SD cold boot and long-run qualification']}
(task/'verification.json').write_text(json.dumps(document,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print('Saved measured HDMI stream and routed-build verification')
