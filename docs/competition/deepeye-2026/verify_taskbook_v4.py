"""Static document, arithmetic and dependency checks. Does not run any product test."""
from pathlib import Path
import json,re,math,hashlib
from pypdf import PdfReader

base=Path(__file__).parent
s=(base/'taskbook_v4.md').read_text(encoding='utf-8')
c=json.loads((base/'simulation_contract_v4.json').read_text(encoding='utf-8'))
p=json.loads((base/'execution_plan_v4.json').read_text(encoding='utf-8'))
checks={}
def check(name,condition):
    checks[name]=bool(condition)
    if not condition:raise AssertionError(name)

cards=re.findall(r'^### ([RABCG]\d\d) ',s,re.M)
check('29_unique_cards_equal_DAG',len(cards)==len(set(cards))==29 and set(cards)==set(p['tasks']))
check('all_product_tasks_not_run',all(t['status']=='not_run' for t in p['tasks'].values()))
check('v4_version',p['task_version']==c['task_version']==4 and '版本4，统筹A' in s)
visiting=set();seen=set()
def visit(k):
    if k in seen:return
    check('dependency_exists_'+k,k in p['tasks'])
    check('acyclic_'+k,k not in visiting)
    visiting.add(k)
    for dep in p['tasks'][k]['dependencies']:visit(dep)
    visiting.remove(k);seen.add(k)
for k in p['tasks']:visit(k)
check('G03_software_does_not_wait_for_its_hardware_bridge','G09' not in p['tasks']['G03']['dependencies'])
check('HIL_system_requires_integrated_3d','G06' in p['tasks']['A02']['dependencies'])
check('standard_release_requires_export','G08' in p['tasks']['A04']['dependencies'])
check('A_only_board',p['hardware_owner']==c['physical_board_owner']=='A')

types=c['abi']['types'];over=c['abi']['fixed_overhead_bytes']
check('3d_command_payload_sum',sum([4,2,1,2,2,1,2,2])==types['control3d']['payload_bytes']==16)
check('3d_ack_payload_sum',sum([4,2,1,1,2,2,1,2,1,2,1,1])==types['ack3d']['payload_bytes']==20)
check('3d_state_payload_sum',sum([4,2,2,2,1,1,2,2,2,1,1])==types['state3d']['payload_bytes']==20)
for typ in ('control3d','ack3d','state3d'):
    check('frame_length_'+typ,types[typ]['total_bytes']==types[typ]['payload_bytes']+over and types[typ]['payload_bytes']<=32)
wire=c['wire_bytes']; normal=sum(types[x]['total_bytes'] for x in ['telem','state3d','control3d','ack3d','event'])
check('normal_HIL_includes_both_directions',normal==wire['normal_hil']==150)
check('config_HIL_includes_config_ack',normal+24+32==wire['config_hil']==206)
check('retry_HIL_includes_full_second_pair',normal+30+34==wire['control_retry_hil']==214)
check('event_retry_separate',normal+20==wire['event_retry_hil']==170)
budgets={}
for name,profile in c['profiles'].items():
    budgets[name]={}
    for scenario,n in wire.items():
        occupied=n*profile['line_bits_per_byte']/profile['baud']+profile['guard_total_s']
        budgets[name][scenario]={'wire_bytes':n,'wire_plus_guard_seconds':occupied,'fraction_of_window':occupied/profile['window_s']}
        check('wire_plus_guard_fits_'+name+'_'+scenario,occupied<=profile['window_s'])

fast=c['profiles']['fast_9600'];slot=fast['slots_ms'];ends={}
for key,typ in [('event','event'),('telem','telem'),('control','control3d'),('ack','ack3d'),('state','state3d'),('retry_control','control3d'),('retry_ack','ack3d'),('config','config'),('config_ack','config_ack')]:
    ends[key]=slot[key]+types[typ]['total_bytes']*10/9600*1000
for chain in [['event','telem','control','ack','state','retry_control','retry_ack'],['event','telem','control','ack','state','config','config_ack']]:
    check('fast_slots_no_overlap_'+chain[-1],all(ends[a]<=slot[b] for a,b in zip(chain,chain[1:])) and ends[chain[-1]]<500)
check('all_rings_larger_equal',math.isclose(c['drill']['ring_diameter_m']/c['drill']['max_diameter_m'],1.25))
check('noise_formula_matches',math.isclose(22.5*math.sqrt(25),c['sensor']['vibration_noise_sigma_ug']))
check('real_vs_assumed_detection_is_explicit','8m是最大模型支持，不是硬保证的探测距离' in s and '厂家未公开这些精度' in s)
check('no_2d_fallback',c['game_quality']['fallback_2d_allowed'] is False and '不能退2D' in s)
check('multi_topology_explicit',all(x in s for x in ['HIL_PC_FPGA','PC_DIRECT','FPGA_LOCAL']))
check('pitch_and_yaw_both_present','captured_pitch2' in s and 'captured_yaw2' in s)
check('no_foreknowledge_inputs',all(x in c['forbidden_controller_inputs'] for x in ['screen_capture','map_seed','truth_collision_query','oracle_route']))
check('whole_drill_exit','钻体完全离开指定面后记arrived' in s)
check('correct_section_structure',len(re.findall(r'^## \d+ ',s,re.M))==15)

reader=PdfReader(base/'deepeye_taskbook_v4.pdf')
text='\n'.join(page.extract_text() or '' for page in reader.pages)
check('pdf_contains_all_cards',all(re.search(r'\b'+k+r'\s',text) for k in cards))
check('pdf_major_content_present',all(x in text for x in ['游戏级三维','CONTROL3D','PC_DIRECT','ADXL355','G09']))
check('pdf_no_replacement_glyph','\ufffd' not in text)
file_hashes={n:hashlib.sha256((base/n).read_bytes()).hexdigest() for n in ['taskbook_v4.md','deepeye_taskbook_v4.pdf','simulation_contract_v4.json','execution_plan_v4.json','research_v4.md','revision_v4.md','architecture_v4.png']}
result={'scope':'static document/math/DAG/PDF text only; no game, RTL, AI or board execution','status':'passed','checks':checks,'pages':len(reader.pages),'cards':len(cards),'wire_budget_recomputed':budgets,'fast_slot_end_ms':ends,'files_sha256':file_hashes,'visual_qa':'pending_render_and_manual_inspection','product_all_stages':'not_run'}
previous_path=base/'checks_v4.json'
if previous_path.exists():
    previous=json.loads(previous_path.read_text(encoding='utf-8'))
    qa=previous.get('visual_qa')
    if isinstance(qa,dict) and qa.get('pdf_sha256')==file_hashes['deepeye_taskbook_v4.pdf'] and qa.get('pages')==len(reader.pages):
        result['visual_qa']=qa
(base/'checks_v4.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'document_checks_passed':sum(checks.values()),'pages':len(reader.pages),'cards':len(cards),'visual_qa':result['visual_qa'] if isinstance(result['visual_qa'],str) else result['visual_qa']['status'],'runtime':'not_run'},ensure_ascii=False))
