#!/usr/bin/env python3
"""Refit the published cost model from retained development labels; no PLN runs."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'src'))
from pln_cost.cost_model import fit,predict,structure_group
from pln_cost.cost_features import FEATURE_NAMES


def error_metrics(model,rows):
    errors=[];apes=[]
    for row in rows:
        estimate=predict(model,[row['features'][f] for f in FEATURE_NAMES])
        if estimate is None:raise ValueError('Invalid prediction')
        ratio=estimate/row['median_cpu_ns']
        errors.append(abs(math.log(ratio)));apes.append(abs(ratio-1))
    return dict(rows=len(rows),mean_absolute_log_error=statistics.mean(errors),
                median_absolute_percentage_error=100*statistics.median(apes))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,help='Optional new model file; never overwrites the benchmark model')
    args=ap.parse_args()
    data=PROJECT/'data/training/expansion-costs.jsonl'
    original=json.loads((PROJECT/'results/benefit-benchmark/run001/model.json').read_text())
    digest=hashlib.sha256(data.read_bytes()).hexdigest()
    if digest!=original['data_sha256']:raise ValueError('Training data changed')
    all_rows=[json.loads(x) for x in data.read_text().splitlines()]
    if any(r['split']!='development' for r in all_rows):raise ValueError('Non-development training data')
    rows=[r for r in all_rows if r['fit_eligible']]
    groups=sorted({structure_group(r) for r in rows})
    validation=[]
    for alpha in (.001,.01,.1,1.):
        folds=[]
        for group in groups:
            model=fit([r for r in rows if structure_group(r)!=group],alpha)
            folds.append(dict(group=group,**error_metrics(model,[r for r in rows if structure_group(r)==group])))
        validation.append(dict(alpha=alpha,folds=folds,score=statistics.mean(f['mean_absolute_log_error'] for f in folds)))
    chosen=min(validation,key=lambda r:r['score'])
    model=fit(rows,chosen['alpha'])
    model.update(training_rows=len(rows),excluded_unresolved_rows=len(all_rows)-len(rows),
        development_structures=groups,data_sha256=digest,split_manifest_sha256=original['split_manifest_sha256'])
    # Floating-point libraries can affect the last bits, so verify numerical parity.
    if model['alpha']!=original['alpha']:raise ValueError('Selected regularization changed')
    for name in ('means','scales','weights'):
        if not all(math.isclose(a,b,rel_tol=1e-9,abs_tol=1e-10) for a,b in zip(model[name],original[name],strict=True)):
            raise ValueError('Refit differs from frozen model: '+name)
    if not math.isclose(model['intercept'],original['intercept'],rel_tol=1e-9,abs_tol=1e-10):
        raise ValueError('Refit intercept differs')
    if args.output:
        with args.output.open('x') as stream:stream.write(json.dumps(model,indent=2)+'\n')
    print(json.dumps(dict(passed=True,training_rows=len(rows),excluded=len(all_rows)-len(rows),alpha=model['alpha'],
        frozen_model_unchanged=True),indent=2))


if __name__=='__main__':main()
