#!/usr/bin/env python3
"""Post-run artifact, proof, coverage and aggregate audit; no native experiments."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics
import sys

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'src'))
from pln_cost.benefit_benchmark import schedule, summarize, coverage, check_stats
from pln_cost.budget import check_result
from pln_cost.expansion import marked
from pln_cost.sexpr import read_case


def load(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run-id',required=True)
    args=ap.parse_args()
    if not args.run_id.replace('-','').replace('_','').isalnum():ap.error('Simple run ID required')
    root=PROJECT/'results/benefit-benchmark'/args.run_id
    dest=root/'measurement'
    report=load(dest/'report.json');qualification=load(root/'qualification-report.json');freeze=load(root/'freeze.json')
    if not report['passed'] or not report['completed'] or report['errors'] or not qualification['passed']:
        raise ValueError('Expected completed valid batch; partial/invalid data require separate review')
    for path,expected in [(root/'freeze.json',report['freeze_sha256']),
                          (root/'qualification-report.json',report['qualification_report_sha256'])]:
        if sha(path)!=expected:raise ValueError(f'Changed metadata: {path}')
    checks=0
    for base,hashes in [(PROJECT,freeze['project_sources']),(root,freeze['artifacts']),(root,qualification['audit_sha256'])]:
        for name,expected in hashes.items():
            if sha(base/name)!=expected:raise ValueError(f'Changed frozen file: {name}')
            checks+=1
    if report['provenance_before']!=report['provenance_after'] or report['provenance_before']!=freeze['provenance']:
        raise ValueError('Runtime provenance mismatch')
    protocol=load(root/'protocol.json');entries=load(root/'manifest.json');jobs=load(root/'schedule.json')
    if schedule(entries,protocol)!=jobs or len(jobs)!=protocol['planned_measurements']:
        raise ValueError('Schedule mismatch')
    runs=[json.loads(line) for line in (dest/'runs.jsonl').read_text().splitlines()]
    coverage(jobs,runs,complete=True)
    counts=Counter((r['case'],r['budget_ns'],r['mode']) for r in runs)
    if len(counts)!=27*8*4 or set(counts.values())!={12}:raise ValueError('Wrong cell coverage')
    cases={e['name']:(read_case((root/e['fixture']).read_text()),e) for e in entries}
    config=load(root/'qualification-config.json');audits={}
    for e in entries:
        for mode in protocol['policies']:
            folder=root/'audits'/e['name']/mode
            audits[(e['name'],mode)]=(load(folder/'states.json'),(folder/'audit.stdout.txt').read_text(),load(folder/'counter-prefixes.json'))
    artifact_checks=proofs=0
    for i,row in enumerate(runs):
        folder=dest/'runs'/f"{row['id']:05d}"
        if load(folder/'result.json')!=row:raise ValueError('Individual/JSONL mismatch')
        execution=load(folder/'query.execution.json')
        for file,k in [('query.metta','fixture_sha256'),('query.stdout.txt','stdout_sha256'),('query.stderr.txt','stderr_sha256')]:
            if sha(folder/file)!=execution[k]:raise ValueError(f'Changed native artifact: {folder/file}')
            artifact_checks+=1
        if execution['returncode']!=0 or execution['timed_out'] or (folder/'query.stderr.txt').read_text().strip():
            raise ValueError('Invalid execution in passed batch')
        case,entry=cases[row['case']];states,trace,prefixes=audits[(row['case'],row['mode'])]
        log=(folder/'query.stdout.txt').read_text()
        metrics,cert,checked=check_result(log,row['budget_ns'],states,trace,case,freeze['native_library_sha256'],
            entry['fixture_sha256'],config['success'])
        if metrics!=row['result']:raise ValueError('Metrics differ from raw output and audited proof prefix')
        stats=marked(log,'BENEFIT_STATS')[0];check_stats(stats,metrics,prefixes)
        if stats!=row['selector_stats']:raise ValueError('Telemetry differs from raw output')
        if cert is not None:
            if load(folder/'certificate.json')!=cert or load(folder/'proof-replay.json')!=checked:
                raise ValueError('Proof artifact differs from independently replayed native trace prefix')
            proofs+=1
        elif (folder/'certificate.json').exists() or (folder/'proof-replay.json').exists():
            raise ValueError('Unexpected proof artifact')
        if (i+1)%1000==0:print(f'Audited saved results {i+1}/{len(runs)}',flush=True)
    comparisons=[protocol['primary_comparison']]+protocol['secondary_comparisons']
    reconstructed=summarize(jobs,runs,comparisons)
    if reconstructed!=load(dest/'summary.json'):raise ValueError('Saved aggregate mismatch')
    # Independently count split/budget totals and paired outcomes from raw rows.
    aggregates=defaultdict(lambda:Counter())
    pair_rows=defaultdict(dict)
    for row in runs:
        r=row['result'];k=(row['split'],row['budget_ns'],row['mode'])
        aggregates[k]['runs']+=1;aggregates[k]['successes']+=int(r['verified_success'])
        pair_rows[(row['split'],row['case'],row['endpoint'],row['budget_ns'],row['repetition'])][row['mode']]=r
    for group in reconstructed['split_totals']:
        c=aggregates[(group['split'],group['budget_ns'],group['mode'])]
        if c['runs']!=group['planned'] or c['successes']!=group['verified_successes']:
            raise ValueError('Independent aggregate mismatch')
    paired={}
    for split in ('development','reserved'):
        for left,right in comparisons:
            outcomes=Counter()
            for (s,case,endpoint,budget,rep),values in pair_rows.items():
                if s!=split or endpoint!='budget':continue
                a,b=values[left]['verified_success'],values[right]['verified_success']
                outcomes['both' if a and b else 'left_only' if a else 'right_only' if b else 'neither']+=1
            saved=Counter()
            for row in reconstructed['paired']:
                if (row['split'],row['left'],row['right'],row['endpoint'])==(split,left,right,'budget'):
                    saved.update(row['outcomes'])
            if outcomes!=saved:raise ValueError('Independent paired count mismatch')
            paired[f'{split}:{left}/{right}']=dict(outcomes)
    latency=[]
    for entry in entries:
        groups={m:sorted([r for r in runs if r['case']==entry['name'] and r['endpoint']=='generous' and r['mode']==m],
                         key=lambda r:r['repetition']) for m in protocol['policies']}
        if any(len(v)!=12 or not all(r['result']['verified_success'] for r in v) for v in groups.values()):
            raise ValueError('This latency table requires complete generous success; failures must not be hidden')
        row=dict(case=entry['name'],split=entry['split'],median_cpu_ms={m:statistics.median(r['result']['engine_cpu_ns']/1e6 for r in rs) for m,rs in groups.items()},comparisons={})
        for left,right in comparisons:
            ratios=[a['result']['engine_cpu_ns']/b['result']['engine_cpu_ns'] for a,b in zip(groups[left],groups[right],strict=True)]
            row['comparisons'][f'{left}/{right}']=dict(paired_ratios=ratios,median=statistics.median(ratios),
                faster=sum(r<1 for r in ratios),equal=sum(r==1 for r in ratios),slower=sum(r>1 for r in ratios),
                quartiles=statistics.quantiles(ratios,n=4,method='inclusive'))
        b=audits[(entry['name'],'B')][0];bc=audits[(entry['name'],'BC')][0]
        row['B_BC_same_state_sequence']=[x['state'] for x in b]==[x['state'] for x in bc]
        latency.append(row)
    diagnostic={}
    for mode in protocol['policies']:
        rows=[r for r in runs if r['endpoint']=='generous' and r['mode']==mode]
        diagnostic[mode]=dict(
            median_selector_fraction=statistics.median(r['selector_stats'][5]/r['result']['engine_cpu_ns'] for r in rows),
            median_descriptor_fraction=statistics.median(r['selector_stats'][2]/r['result']['engine_cpu_ns'] for r in rows),
            median_cost_feature_fraction=statistics.median(r['selector_stats'][4]/r['result']['engine_cpu_ns'] for r in rows),
            coverage_fallbacks=sum(r['selector_stats'][6] for r in runs if r['mode']==mode),
            prediction_fallbacks=sum(r['selector_stats'][7] for r in runs if r['mode']==mode),
            maximum_overshoot_ns=max(r['result']['overshoot_ns'] for r in runs if r['mode']==mode))
    analysis=dict(passed=True,completed_runs=len(runs),frozen_hash_checks=checks,native_artifact_hash_checks=artifact_checks,
        replayed_detected_proofs=proofs,statuses=dict(Counter(r['result']['status'] for r in runs)),
        paired_tight_budget_outcomes=paired,latency=latency,diagnostic=diagnostic,
        input_hashes={n:sha(dest/n) for n in ('runs.jsonl','report.json','summary.json')},
        analysis_script_sha256=sha(Path(__file__)))
    (dest/'verified-analysis.json').write_text(json.dumps(analysis,indent=2)+'\n')
    print(json.dumps({k:analysis[k] for k in ('passed','completed_runs','native_artifact_hash_checks','replayed_detected_proofs','statuses','diagnostic')},indent=2),flush=True)


if __name__=='__main__':main()
