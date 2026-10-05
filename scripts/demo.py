#!/usr/bin/env python3
"""Explain one captured query, or explicitly rerun it in native PLN for correctness.

The default reads saved evidence only. A native rerun is a smoke check, not a new
performance result. Neither mode changes the original measured evidence.
"""
import argparse
from functools import partial
import hashlib
import json
from pathlib import Path
import sys
import tempfile

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'src'))
from pln_cost.benefit_selection import choose,selection_fixture
from pln_cost.benefit_benchmark import check_stats
from pln_cost.budget import check_result
from pln_cost.cost_selection import audit_trace
from pln_cost.expansion import marked
from pln_cost.runtime import Runtime
from pln_cost.sexpr import read_case
from pln_cost.validation import clean_completion


def load(path):return json.loads(path.read_text())
def show(x):return '('+' '.join(map(show,x))+')' if isinstance(x,list) else str(x)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--case',default='n001-canonical_ids')
    ap.add_argument('--mode',choices=('N','B','BO','BC'),default='N')
    ap.add_argument('--native',action='store_true',help='Run one query with the pinned runtime; does not benchmark speed')
    args=ap.parse_args()
    root=PROJECT/'results/benefit-benchmark/run001'
    entries=load(root/'manifest.json')
    entry=next((e for e in entries if e['name']==args.case),None)
    if entry is None:ap.error('Unknown case; see results/benefit-benchmark/run001/manifest.json')
    case=read_case((root/entry['fixture']).read_text());config=load(root/'qualification-config.json')
    model=load(root/'model.json');freeze=load(root/'freeze.json')
    folder=root/'audits'/args.case/args.mode
    log=(folder/'audit.stdout.txt').read_text()
    states,selected,cert,proof=audit_trace(log,case,config,model,args.mode,freeze['native_library_sha256'],
        entry['fixture_sha256'],selection_reference=partial(choose,query=case['query'],marginals={}))
    if states!=load(folder/'states.json') or cert!=load(folder/'certificate.json') or proof!=load(folder/'proof-replay.json'):
        raise ValueError('Captured proof/state mismatch')
    print(f'Case: {args.case}; selector: {args.mode}; query: {show(case["query"])}')
    print('Initial BB:',', '.join(show(r[1][0]) for r in states[0]['state']['beliefs']))
    print('Initial PQT:',', '.join(show(r[1][0]) for r in states[0]['state']['tasks']))
    for i,record in enumerate(selected):
        before,after=states[i]['state'],states[i+1]['state']
        added=[r for r in after['beliefs'] if r not in before['beliefs']]
        print(f'Expansion {i+1}: select {show(record[1][0])}')
        print('  Added beliefs:',', '.join(show(r[1][0]) for r in added) or '(none)')
        print('  PQT:',', '.join(show(r[1][0]) for r in after['tasks']))
    print('Verified answer:',json.dumps(proof['answer']))
    if args.native:
        # The frozen bootstrap calls current Python. Demand identical online
        # Python implementations before using it for a native reproduction.
        for name in ('src/pln_cost/benefit_selection.py','src/pln_cost/benefit_signals.py','src/pln_cost/proof.py'):
            if hashlib.sha256((PROJECT/name).read_bytes()).hexdigest()!=freeze['project_sources'][name]:
                raise ValueError('Online code differs from the original: '+name)
        runtime=Runtime(PROJECT,PROJECT/'configs/runtime.json');runtime.verify()
        with tempfile.TemporaryDirectory(prefix='pln-demo-') as temp:
            fixture=Path(temp)/'query.metta'
            fixture.write_text(selection_fixture(case,config,1_000_000_000,model,args.mode))
            result=runtime.run(fixture,preload_pln=True,library_path=root/'lib_pln.quiet.metta',bootstrap_path=root/'bootstrap.pl')
        if not clean_completion(result):raise RuntimeError(result['stderr'] or result['stdout'])
        metrics,_,_=check_result(result['stdout'],1_000_000_000,states,log,case,freeze['native_library_sha256'],entry['fixture_sha256'],config['success'])
        check_stats(marked(result['stdout'],'BENEFIT_STATS')[0],metrics,load(folder/'counter-prefixes.json'))
        if not metrics['verified_success']:raise ValueError('Native correctness check failed')
        print('Native correctness check passed:',metrics['completed_expansions'],'expansions. Not a timing comparison.')


if __name__=='__main__':main()
