"""Narrow v2 correction checks; does NOT rerun v1 author/independent suites.

python -B independent_c33_provenance_checks.py PUBLIC_DIR V1_ACTUAL_JSON OUTPUT_DIR
V1_ACTUAL_JSON is the pinned retained output, never produced by executing v1.
"""
import hashlib,json,pathlib,sys,types

public=pathlib.Path(sys.argv[1]).resolve()
baseline_path=pathlib.Path(sys.argv[2]).resolve()
out=pathlib.Path(sys.argv[3]).resolve()
assert out!=public and public not in out.parents
out.mkdir(parents=True,exist_ok=True)
runtime=(public/'retired_input_diagnostic.py').read_bytes()
assert hashlib.sha256(runtime).hexdigest()=='532f27b1c56e806e0989a30f27db1d7685278b2f9e70654a3a3d5900fca42874'
raw=(public/'retired-source70.json').read_bytes()
assert hashlib.sha256(raw).hexdigest()=='63616e2915edc5a2ef6ed592e8f9830ce77a635aaf883ab964aa4dbd5fd1910c'
baseline_bytes=baseline_path.read_bytes()
assert hashlib.sha256(baseline_bytes).hexdigest()=='7564f32602731a19d279b8eae841bf8173681d878f56ae239721673e1351a3e6'
baseline=json.loads(baseline_bytes)
m=types.ModuleType('c33_provenance_v2_under_review')
exec(compile(runtime,str(public/'retired_input_diagnostic.py'),'exec'),m.__dict__)
actual_bytes=m.diagnose_json(raw)
(out/'actual-diagnostic-v2.json').write_bytes(actual_bytes)
actual=json.loads(actual_bytes)
results=[]
def ok(name,**facts):
    r=dict(name=name,passed=True,**facts);results.append(r)
    print(json.dumps(r,sort_keys=True),flush=True)

removed={'frozen_c31_source_version_incompatible','frozen_c31_fixed_binding_only'}
expected=json.loads(baseline_bytes)
expected['diagnostic_kind']='single_pinned_retired_source70_v2'
expected['missing_codes']=[s for s in expected['missing_codes'] if s not in removed]
assert actual==expected
assert {k for k in baseline if baseline[k]!=actual[k]}=={'diagnostic_kind','missing_codes'}
assert set(baseline['missing_codes'])-set(actual['missing_codes'])==removed
assert len(actual['missing_codes'])==8
ok('new_v2_exact_changed_output',changed_fields=['diagnostic_kind','missing_codes'],removed_codes=sorted(removed),other_fields_exactly_equal=True)

assert actual['input_status']=='INPUT_UNAVAILABLE' and actual['status']=='STOP'
assert actual['projection'] is None and actual['authorization']=='none'
assert actual['c30_called'] is False and actual['c31_called'] is False and actual['core_ran'] is False
assert actual['native_interval_atomic'] is False and actual['historical_only'] is True
assert {'original_book_owner_identity_missing','original_em_scope_receipt_missing','live_current_pose_capture_missing','original_admission_capture_times_missing','executed_action_receipts_missing','actual_commit_point_missing','verified_board_boot_missing','retired_not_current'}==set(actual['missing_codes'])
ok('new_v2_true_missing_evidence_still_stops',projection=None,c30_called=False,c31_called=False,core_ran=False)

prov=json.loads((public/'book-provenance.json').read_bytes())
contract=json.loads((public/'minimum-evidence-contract.json').read_bytes())
assert contract['frozen_C31']['book_code_provenance']==prov
assert prov['book_bytes_equal'] is True
assert prov['contract_commit']=='54e1fd6c5795cc2f1247866dd8783331f615ef66'
assert prov['actual_source70_runtime_commit']==actual['source_commit']=='4dc91fd24531b3df53fc916e8b7f509ad524592c'
assert prov['sha256']=='624c84f8de949c7c078ca0b7afa84c295804d7bc881527e9b91c38ba645004ef'
assert prov['git_blob']=='be584260af61fa6bd4800914e3dd37323e734bf8'
assert not removed.intersection(contract['historical_diagnostic']['additional_interface_limits'])
assert contract['historical_diagnostic']['kind']==actual['diagnostic_kind']
assert contract['current_mapping']['completion_observed_qpc_ns_to_C30_action_at'] is None
assert (public/'retired-source70.json').read_bytes()==raw
ok('new_v2_contract_runtime_labels_distinct_without_fabricated_projection',book_schema=actual['book_schema'],retained_runtime_commit=actual['source_commit'])
summary={'scope':'Narrow v2 provenance/output change only; v1 five/six groups not rerun or relabelled','passed':len(results),'failed':0,'results':results,'actual_output_bytes':len(actual_bytes),'actual_output_sha256':hashlib.sha256(actual_bytes).hexdigest(),'v1_actual_output_sha256':hashlib.sha256(baseline_bytes).hexdigest()}
(out/'narrow-results.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8')
print(json.dumps({k:v for k,v in summary.items() if k!='results'}),flush=True)
