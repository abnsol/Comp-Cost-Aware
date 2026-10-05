#!/usr/bin/env python3
"""Two explicit phases: prepare/qualify, then separately measure a frozen batch.

Prepare never starts the scheduled timing sweep. Measure refuses an existing
measurement directory, unqualified batch, changed sources or changed artifacts.
"""
import argparse
from functools import partial
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import time

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT / "src"))
from pln_cost.benefit_benchmark import schedule, summarize, coverage, expected_counters, check_stats
from pln_cost.benefit_selection import selection_fixture, choose, build_library, bootstrap
from pln_cost.first_answer import quiet_library
from pln_cost.benefit_signals import SCOPE, describe
from pln_cost.budget import check_result
from pln_cost.cost_selection import audit_trace
from pln_cost.expansion import reference_fixture, marked
from pln_cost.proof import key, replay
from pln_cost.qualification import QUERY, kb_records, render_case, static_witness, qualifies
from pln_cost.runtime import Runtime
from pln_cost.selection_workloads import necessary_records
from pln_cost.sexpr import read_case, read_one
from pln_cost.validation import clean_completion


def load(p):
    return json.loads(p.read_text())


def save(p, value):
    p.write_text(json.dumps(value, indent=2) + "\n")


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def verify_hashes(root, hashes):
    for name, expected in hashes.items():
        if sha(root / name) != expected:
            raise ValueError(f"Frozen file changed: {root / name}")


def host_context():
    cpu = Path('/proc/cpuinfo')
    models = sorted({line.split(':',1)[1].strip() for line in cpu.read_text().splitlines()
                     if line.startswith('model name')}) if cpu.exists() else []
    return dict(platform=platform.platform(), parent_python=sys.version,
        cpu_models=models, logical_cpus=os.cpu_count(),
        affinity=sorted(os.sched_getaffinity(0)) if hasattr(os,'sched_getaffinity') else None,
        process_clock=vars(time.get_clock_info('process_time')))


def execute(runtime, out, path, library):
    result = runtime.run(path, preload_pln=True, library_path=library, bootstrap_path=out / 'bootstrap.pl')
    for stream in ('stdout','stderr'):
        path.with_suffix(f'.{stream}.txt').write_text(result[stream])
    save(path.with_suffix('.execution.json'), {
        **{k:v for k,v in result.items() if k not in ('stdout','stderr')},
        'fixture_sha256':sha(path), 'stdout_sha256':sha(path.with_suffix('.stdout.txt')),
        'stderr_sha256':sha(path.with_suffix('.stderr.txt'))})
    if not clean_completion(result):
        raise RuntimeError(f"Invalid execution: {path}")
    return result['stdout']


def qualified_shape(case, family, width, distractors=4):
    if family == 'alternative':
        expected = kb_records(width)
    elif family == 'necessary':
        expected = necessary_records(width, distractors=distractors)
    else:
        raise ValueError('Unknown workload family')
    if (case['query'] != QUERY or case['marginals'] != {} or
            sorted(map(key,case['inputs'])) != sorted(map(key,expected))):
        raise ValueError('Fixture violates closed qualified family')
    # Exact family comparison above establishes the scope declaration; describe
    # alone is NOT a full PLN rule-coverage detector.
    desc = describe(dict(tasks=case['inputs'],beliefs=case['inputs']),QUERY,scope=SCOPE,marginals={})
    if desc['coverage'] != SCOPE:
        raise ValueError('Qualified fixture rejected by descriptors')


def prepare(out):
    out.mkdir(parents=True,exist_ok=False)
    report = dict(passed=False, timing_sweep_started=False, audits=[], authored_witnesses=[],
                  smoke_checks=[], host=host_context())
    try:
        protocol = load(PROJECT/'configs/benefit-selection-comparison.json')
        save(out/'protocol.json',protocol)
        reference = PROJECT / protocol['reference_batch']
        model_path = PROJECT / protocol['model_path']
        if sha(model_path) != protocol['model_sha256']:
            raise ValueError('Changed frozen cost model')
        runtime = Runtime(PROJECT,PROJECT/'configs/runtime.json')
        report['provenance_before'] = runtime.verify()
        source = (runtime.pln/'lib_pln.metta').read_text()
        source_hash = sha(runtime.pln/'lib_pln.metta')
        report['native_library_sha256'] = source_hash
        (out/'bootstrap.pl').write_text(bootstrap(PROJECT))
        for audit in (False,True):
            text,patch = build_library(source,audit)
            name = 'lib_pln.audit' if audit else 'lib_pln.quiet'
            (out/(name+'.metta')).write_text(text)
            (out/(name+'.diff')).write_text(patch)
        (out/'lib_pln.native.metta').write_text(quiet_library(source)[0])
        shutil.copyfile(runtime.pln/'LICENSE',out/'PLN-LICENSE.txt')
        shutil.copyfile(model_path,out/'model.json')
        config = load(PROJECT/protocol['qualification_config_path'])
        save(out/'qualification-config.json',config)
        model = load(out/'model.json')
        # Reproduce the already published 27 cases. These are now known cases,
        # not a fresh held-out evaluation for any subsequent method changes.
        original_entries = load(reference/'manifest.json')
        fixtures = out/'fixtures'; fixtures.mkdir()
        entries = []
        expected = {protocol['model_path']:sha(model_path),
                    str((reference/'manifest.json').relative_to(PROJECT)):sha(reference/'manifest.json')}
        for old in original_entries:
            src = reference/old['fixture']
            if sha(src)!=old['fixture_sha256']:
                raise ValueError('Reference fixture changed')
            dst = fixtures/(old['name']+'.metta');shutil.copyfile(src,dst)
            expected[str(src.relative_to(PROJECT))] = sha(src)
            entries.append(dict(name=old['name'],family=old['family'],split=old['split'],
                width=old['width'],distractors=old.get('distractors',4),
                fixture=str(dst.relative_to(out)),fixture_sha256=sha(dst)))
        if len(entries)!=27:
            raise ValueError('Expected the 27 published benchmark cases')
        report['evaluation_status']='Reproduction of known cases; not a new holdout'
        cases = {}
        witness_dir = out/'authored-witnesses'; witness_dir.mkdir()
        for entry in entries:
            path=out/entry['fixture']; case=read_case(path.read_text()); cases[entry['name']]=case
            if sha(path)!=entry['fixture_sha256']:
                raise ValueError('Fixture copy changed')
            qualified_shape(case,entry['family'],entry['width'],entry.get('distractors',4))
            routes = ([('A',[1,3,4]),('B',[2,5,6])] if entry['family']=='alternative'
                      else [('required',[1,2,3])])
            for label,ids in routes:
                cert=static_witness(case,ids,source_hash,entry['fixture_sha256'])
                checked=replay(cert,case,source_hash,entry['fixture_sha256'])
                if not qualifies(checked,config['success']):
                    raise ValueError('Authored witness failed replay')
                save(witness_dir/f"{entry['name']}-{label}.json",dict(certificate=cert,replay=checked))
                report['authored_witnesses'].append(dict(case=entry['name'],route=label,verified=True))
        save(out/'manifest.json',entries)
        jobs=schedule(entries,protocol)
        if len(jobs)!=protocol['planned_measurements']:
            raise ValueError('Planned query count mismatch')
        save(out/'schedule.json',jobs)
        sources={str(p.relative_to(PROJECT)):sha(p) for folder in ('src','scripts','configs','tests')
                 for p in sorted((PROJECT/folder).rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
        artifacts={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file()}
        frozen=dict(project_sources={**expected,**sources},artifacts=artifacts,
                    native_library_sha256=source_hash,provenance=report['provenance_before'])
        save(out/'freeze.json',frozen)  # BEFORE reserved native execution; never rewritten.
        report['freeze_sha256']=sha(out/'freeze.json')
        report['planned_measurements']=len(jobs)
        save(out/'qualification-report.json',report)
        for entry in entries:
            name=entry['name']; case=cases[name]; paths={}
            for mode in protocol['policies']:
                print(f"Qualify {entry['split']}: {name} {mode}",flush=True)
                folder=out/'audits'/name/mode;folder.mkdir(parents=True)
                path=folder/'audit.metta'
                path.write_text(selection_fixture(case,config,protocol['audit_budget_ns'],model,mode))
                log=execute(runtime,out,path,out/'lib_pln.audit.metta')
                states,selected,cert,checked=audit_trace(log,case,config,model,mode,source_hash,
                    entry['fixture_sha256'],selection_reference=partial(choose,query=case['query'],marginals={}))
                result,_,_=check_result(log,protocol['audit_budget_ns'],states,log,case,source_hash,
                    entry['fixture_sha256'],config['success'],audit=True)
                if result['status'] not in ('success','exhausted'):
                    raise ValueError('Audit did not cover a complete logical trajectory')
                save(folder/'states.json',states);save(folder/'certificate.json',cert);save(folder/'proof-replay.json',checked)
                paths[mode]=[s['state'] for s in states]
                if mode=='BO' and paths['BO']!=paths['B']:
                    raise ValueError('Overhead-only arm changed choices')
                transitions=0
                ref=folder/'native-transitions.metta'
                ref.write_text(''.join(reference_fixture(s['state'],c).replace('COST_REFERENCE',f'TRANSITION_{i}')
                    for i,(s,c) in enumerate(zip(states[:-1],selected,strict=True))))
                ref_log=execute(runtime,out,ref,out/'lib_pln.native.metta')
                actual=[read_one(line) for line in ref_log.splitlines() if line.startswith('(TRANSITION_')]
                wanted=[[f'TRANSITION_{i}',[states[i+1]['state'][k] for k in ('tasks','beliefs')]] for i in range(len(selected))]
                if actual!=wanted:
                    raise ValueError('Native one-step transition mismatch')
                transitions=len(actual)
                prefixes=expected_counters(states,model,mode,case['query']);save(folder/'counter-prefixes.json',prefixes)
                quiet=folder/'quiet.metta'
                quiet.write_text(selection_fixture(case,config,protocol['audit_budget_ns'],model,mode))
                qlog=execute(runtime,out,quiet,out/'lib_pln.quiet.metta')
                metrics,_,_=check_result(qlog,protocol['audit_budget_ns'],states,log,case,source_hash,
                    entry['fixture_sha256'],config['success'])
                check_stats(marked(qlog,'BENEFIT_STATS')[0],metrics,prefixes)
                if metrics['status']!=result['status'] or metrics['completed_expansions']!=len(selected):
                    raise ValueError('Quiet/audit trajectory mismatch')
                report['audits'].append(dict(case=name,split=entry['split'],mode=mode,expansions=len(selected),
                    proof_verified=cert is not None,status=result['status'],native_transition_checks=transitions,
                    quiet_accounting_checked=True))
                save(out/'qualification-report.json',report)
        # Exercise the same measurement parser on an empty completed prefix.
        first=entries[0];case=cases[first['name']]
        for mode in protocol['policies']:
            folder=out/'audits'/first['name']/mode;path=folder/'zero.metta'
            path.write_text(selection_fixture(case,config,0,model,mode))
            log=execute(runtime,out,path,out/'lib_pln.quiet.metta')
            metrics,_,_=check_result(log,0,load(folder/'states.json'),(folder/'audit.stdout.txt').read_text(),
                case,source_hash,first['fixture_sha256'],config['success'])
            check_stats(marked(log,'BENEFIT_STATS')[0],metrics,load(folder/'counter-prefixes.json'))
            if metrics['status']!='deadline' or metrics['completed_expansions']!=0:
                raise ValueError('Zero budget performed work')
            report['smoke_checks'].append(dict(mode=mode,zero_budget=True))
        verify_hashes(PROJECT,frozen['project_sources']);verify_hashes(out,frozen['artifacts'])
        report['provenance_after']=runtime.verify()
        if report['provenance_before']!=report['provenance_after']:
            raise ValueError('Runtime changed during qualification')
        report['audit_sha256']={str(p.relative_to(out)):sha(p) for p in sorted((out/'audits').rglob('*')) if p.is_file()}
        report['passed']=True
    except Exception as exc:
        report['error']=f'{type(exc).__name__}: {exc}'
    save(out/'qualification-report.json',report)
    print(json.dumps({k:report.get(k) for k in ('passed','timing_sweep_started','planned_measurements','error')},indent=2),flush=True)
    return 0 if report['passed'] else 1


def measure(out):
    qualification=load(out/'qualification-report.json')
    if not qualification['passed'] or sha(out/'freeze.json')!=qualification['freeze_sha256']:
        raise ValueError('Batch has no intact successful qualification')
    frozen=load(out/'freeze.json')
    verify_hashes(PROJECT,frozen['project_sources']);verify_hashes(out,frozen['artifacts'])
    verify_hashes(out,qualification['audit_sha256'])
    protocol=load(out/'protocol.json'); entries=load(out/'manifest.json'); jobs=load(out/'schedule.json')
    if schedule(entries,protocol)!=jobs or len(jobs)!=protocol['planned_measurements']:
        raise ValueError('Schedule does not match protocol')
    runtime=Runtime(PROJECT,PROJECT/'configs/runtime.json')
    provenance=runtime.verify()
    if provenance!=frozen['provenance'] or sha(runtime.pln/'lib_pln.metta')!=frozen['native_library_sha256']:
        raise ValueError('Runtime differs from qualification')
    dest=out/'measurement';dest.mkdir(exist_ok=False)
    report=dict(passed=False,completed=False,planned=len(jobs),executed=0,errors=[],host=host_context(),
                provenance_before=provenance,qualification_report_sha256=sha(out/'qualification-report.json'),
                freeze_sha256=sha(out/'freeze.json'))
    save(dest/'report.json',report)
    model=load(out/'model.json');config=load(out/'qualification-config.json')
    cases={e['name']:(read_case((out/e['fixture']).read_text()),e) for e in entries}
    audits={}
    for e in entries:
        for mode in protocol['policies']:
            folder=out/'audits'/e['name']/mode
            audits[(e['name'],mode)]=(load(folder/'states.json'),(folder/'audit.stdout.txt').read_text(),load(folder/'counter-prefixes.json'))
    runs=[]
    comparisons=[protocol['primary_comparison']]+protocol['secondary_comparisons']
    try:
        for job in jobs:
            row=dict(job);case,entry=cases[job['case']];states,trace,prefixes=audits[(job['case'],job['mode'])]
            folder=dest/'runs'/f"{job['id']:05d}";folder.mkdir(parents=True)
            path=folder/'query.metta'
            try:
                path.write_text(selection_fixture(case,config,job['budget_ns'],model,job['mode']))
                log=execute(runtime,out,path,out/'lib_pln.quiet.metta')
                metrics,cert,checked=check_result(log,job['budget_ns'],states,trace,case,frozen['native_library_sha256'],
                    entry['fixture_sha256'],config['success'])
                stats=marked(log,'BENEFIT_STATS')[0];check_stats(stats,metrics,prefixes)
                if cert is not None:
                    save(folder/'certificate.json',cert);save(folder/'proof-replay.json',checked)
                row.update(result=metrics,selector_stats=stats)
            except Exception as exc:
                row['error']=f'{type(exc).__name__}: {exc}'
                report['errors'].append(dict(id=job['id'],error=row['error']))
            save(folder/'result.json',row)
            with (dest/'runs.jsonl').open('a') as stream:
                stream.write(json.dumps(row)+'\n')
            runs.append(row);report['executed']=len(runs)
            if len(runs)%25==0 or 'error' in row:
                save(dest/'report.json',report)
                print(f"Measured {len(runs)}/{len(jobs)}; invalid={len(report['errors'])}",flush=True)
            if len(report['errors'])>=3:
                raise RuntimeError('Three invalid executions: stopped without replacement')
        coverage(jobs,runs,complete=True)
        verify_hashes(PROJECT,frozen['project_sources']);verify_hashes(out,frozen['artifacts'])
        verify_hashes(out,qualification['audit_sha256'])
        if sha(out/'qualification-report.json')!=report['qualification_report_sha256'] or sha(out/'freeze.json')!=report['freeze_sha256']:
            raise ValueError('Qualification metadata changed during measurement')
        report['provenance_after']=runtime.verify()
        report['completed']=True
        report['passed']=not report['errors'] and report['provenance_after']==provenance
    except Exception as exc:
        report['error']=f'{type(exc).__name__}: {exc}'
    save(dest/'summary.json',summarize(jobs,runs,comparisons));save(dest/'report.json',report)
    print(json.dumps({k:report.get(k) for k in ('passed','completed','executed','error')},indent=2),flush=True)
    return 0 if report['passed'] else 1


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--phase',required=True,choices=('prepare','measure'))
    ap.add_argument('--run-id',required=True)
    args=ap.parse_args()
    if not args.run_id.replace('-','').replace('_','').isalnum():
        ap.error('Simple run ID required')
    out=PROJECT/'results/benefit-benchmark'/args.run_id
    return prepare(out) if args.phase=='prepare' else measure(out)


if __name__=='__main__':
    raise SystemExit(main())
