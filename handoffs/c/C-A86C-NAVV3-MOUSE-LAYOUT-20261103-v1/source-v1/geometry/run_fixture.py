"""Bounded NEW fixture runner; raw streams and actual exit retained."""
import pathlib,subprocess,sys,json,hashlib,datetime
D=pathlib.Path(__file__).resolve().parent
argv=[sys.executable,'-X','utf8','-B',str(D/'geometry_fixture.py')]
start=datetime.datetime.now(datetime.timezone.utc).isoformat()
r=subprocess.run(argv,cwd=D,capture_output=True,timeout=30)
(D/'run01.stdout').write_bytes(r.stdout);(D/'run01.stderr').write_bytes(r.stderr)
meta=dict(argv=argv,cwd=str(D),started_utc=start,ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),exit_code=r.returncode,source_sha256=hashlib.sha256((D/'geometry_fixture.py').read_bytes()).hexdigest(),source_bytes=(D/'geometry_fixture.py').stat().st_size,product_imports=0,software_fixture=True)
(D/'run01.command.json').write_text(json.dumps(meta,indent=2)+'\n',encoding='utf8')
print(json.dumps(meta,indent=2));print(r.stdout.decode('utf8'));print(r.stderr.decode('utf8'))
raise SystemExit(r.returncode)
