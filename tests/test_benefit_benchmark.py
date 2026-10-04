from collections import Counter, defaultdict
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT/'src'))
from pln_cost.benefit_benchmark import schedule, summarize, coverage, check_stats


class BenefitBenchmarkTests(unittest.TestCase):
    def setUp(self):
        self.protocol=json.loads((PROJECT/'configs/benefit-selection-comparison.json').read_text())
        self.cases=[dict(name='a',split='development'),dict(name='b',split='reserved')]

    def test_schedule_balance_exact_blocks_and_reproducibility(self):
        jobs=schedule(self.cases,self.protocol)
        self.assertEqual(jobs,schedule(self.cases,self.protocol))
        self.assertEqual(len(jobs),2*8*4*12)
        blocks=defaultdict(list)
        for j in jobs:
            blocks[(j['case'],j['budget_ns'],j['repetition'])].append(j['mode'])
        for i in range(0,len(jobs),4):
            self.assertEqual(len({(j['case'],j['budget_ns'],j['repetition']) for j in jobs[i:i+4]}),1)
        for case in self.cases:
            for budget in self.protocol['budgets_ns']+[self.protocol['generous_budget_ns']]:
                orders=[tuple(blocks[(case['name'],budget,r)]) for r in range(12)]
                self.assertEqual(Counter(orders),Counter({tuple(o):3 for o in self.protocol['balanced_arm_orders']}))
                self.assertEqual(Counter(p for o in orders for p in zip(o,o[1:])),Counter({(a,b):3 for a in self.protocol['policies'] for b in self.protocol['policies'] if a!=b}))

    def test_wrong_orders_duplicate_cases_and_budgets_rejected(self):
        bad=deepcopy(self.protocol);bad['balanced_arm_orders'][0]=bad['balanced_arm_orders'][1]
        with self.assertRaises(ValueError):schedule(self.cases,bad)
        with self.assertRaises(ValueError):schedule(self.cases*2,self.protocol)
        bad=deepcopy(self.protocol);bad['budgets_ns'].append(bad['generous_budget_ns'])
        with self.assertRaises(ValueError):schedule(self.cases,bad)

    def test_missing_invalid_and_deadline_are_distinct_and_preserved(self):
        jobs=[dict(id=i,case='x',split='reserved',endpoint='budget',budget_ns=10,repetition=0,mode=m)
              for i,m in enumerate(['N','B','BO','BC'])]
        metrics=dict(status='deadline',verified_success=False,engine_cpu_ns=12,overshoot_ns=2)
        rows=[{**jobs[0],'result':metrics},{**jobs[1],'error':'invalid proof'},
              {**jobs[2],'result':{**metrics,'status':'success','verified_success':True,'engine_cpu_ns':5,'overshoot_ns':0}}]
        partial=summarize(jobs,rows)
        self.assertFalse(partial['completed'])
        self.assertEqual(partial['paired'][0]['outcomes'],{'missing_pair':1})
        self.assertEqual(sum(r['planned'] for r in partial['per_case']),4)
        self.assertEqual(sum(r['invalid'] for r in partial['per_case']),1)
        self.assertEqual(sum(r['missing'] for r in partial['per_case']),1)
        rows.append({**jobs[3],'result':metrics})
        full=summarize(jobs,rows)
        self.assertTrue(full['completed'])
        self.assertEqual(full['paired'][0]['outcomes'],{'invalid_pair':1})
        self.assertIsNone(full['paired'][0]['median_both_success_cpu_ratio'])

    def test_latency_subset_not_presented_as_complete(self):
        jobs=[];rows=[]
        for rep in range(2):
            for mode in ('B','BC'):
                j=dict(id=len(jobs),case='x',split='reserved',endpoint='generous',budget_ns=100,repetition=rep,mode=mode)
                jobs.append(j)
                success=rep==0 or mode=='B'
                rows.append({**j,'result':dict(status='success' if success else 'late_return',verified_success=success,
                    engine_cpu_ns=5 if mode=='BC' and success else 10 if success else 101,overshoot_ns=0 if success else 1)})
        p=summarize(jobs,rows)['paired'][0]
        self.assertEqual(p['outcomes'],{'both':1,'right_only':1})
        self.assertEqual(p['median_both_success_cpu_ratio'],.5)
        self.assertFalse(p['latency_subset_complete'])

    def test_duplicate_out_of_order_or_missing_results_rejected(self):
        jobs=schedule(self.cases,self.protocol)
        row={**jobs[0],'error':'failure'}
        self.assertFalse(coverage(jobs,[row]))
        for rows in ([row,row],[{**jobs[1],'error':'wrong order'}],[dict(jobs[0])]):
            with self.assertRaises(ValueError):coverage(jobs,rows)
        with self.assertRaises(ValueError):coverage(jobs,[row],complete=True)

    def test_telemetry_prefix_and_overlapping_intervals(self):
        metrics=dict(completed_expansions=1,engine_cpu_ns=100)
        prefixes=[[0]*6,[1,4,2,0,0,0]]
        check_stats([1,4,30,2,20,75,0,0,0],metrics,prefixes)
        for stats in ([1,4,30,2,20,40,0,0,0],[1,4,30,1,20,75,0,0,0],[1,4,30,2,20,101,0,0,0]):
            with self.assertRaises(ValueError):check_stats(stats,metrics,prefixes)

    def test_runner_hash_guard_and_closed_shape(self):
        spec=importlib.util.spec_from_file_location('benchmark_runner',PROJECT/'scripts/run_benefit_benchmark.py')
        runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'source';p.write_text('initial')
            hashes={'source':runner.sha(p)};runner.verify_hashes(root,hashes)
            p.write_text('changed')
            with self.assertRaises(ValueError):runner.verify_hashes(root,hashes)
        # Development-width authored fixture; reserved fixtures are not generated here.
        case=dict(query=runner.QUERY,marginals={},inputs=runner.kb_records(4))
        runner.qualified_shape(case,'alternative',4)
        case['inputs'][0][1][1][2]=.8
        with self.assertRaises(ValueError):runner.qualified_shape(case,'alternative',4)


if __name__=='__main__':unittest.main()
