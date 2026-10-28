"""Deterministic tests only; no scientific random stream is generated."""
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from personalized_charging.projection_comparison_study_v1 import run
from personalized_charging.two_driver_exploratory_v1.physical import simulate
from personalized_charging.two_driver_exploratory_v1.schedule import plan
from personalized_charging.two_driver_exploratory_v1.test_independent_fraction import cells, inputs


def fixed_world():
    return {'physics':dict(g0='.568',g1='.548',g2='.4',delta='.005',W='20',epsilon='.005'),
            'users':{'A':dict(theta=.08,p=.3,r=.4,third=.6),
                     'B':dict(theta=.12,p=.2,r=.55,third=.7)}}


class RunnerTests(unittest.TestCase):
    def test_calendar_and_deterministic_cell_ledger(self):
        w=fixed_world()
        for start,end in ((0,16),(16,64),(64,256),(0,3000000)):
            self.assertEqual(sum(run.schedule_count(start,end,p) for p in range(6)),end-start)
        for role_pos in range(6):
            for variant in run.SCHEDULES:
                role,action=plan(role_pos,variant)
                for idx,row in enumerate(cells(role)):
                    one=[0]*12; one[idx]=1
                    actual=run.ledger(w,role,role_pos,one,variant)
                    values=('.568','.548','.4','20')
                    episode=simulate(role,action,**inputs(row,values))
                    baseline=simulate(role,'baseline',**inputs(row,values))
                    self.assertAlmostEqual(actual['gain'],float(baseline.system_cost-episode.system_cost),places=12)
                    self.assertEqual(actual['unmet'],episode.unmet_kwh)
                    observed={(e.driver,e.offer):int(e.accepted) for e in episode.events if e.offer}
                    for user in ('A','B'):
                        for offer in run.OFFERS:
                            key=(user,offer)
                            self.assertEqual(actual['observed'][user][offer],
                                             [observed.get(key,0),int(key in observed)])
                    self.assertEqual(actual['suppressed'],int(role_pos==4 and variant=='natural' and row['p']))

    def test_gate_adapter_disallows_latent_data_and_unknown_failures(self):
        phys=fixed_world()['physics']
        counts={d:{j:(0,0) for j in run.OFFERS} for d in ('A','B')}
        for method in run.DATA_METHODS:
            selected={d:{k:v for k,v in counts[d].items() if method!='two' or k!='third'} for d in counts}
            got=run.call_gate(selected,method,phys)
            self.assertEqual(got['decision'],'ABSTAIN')
            leaked={d:dict(selected[d]) for d in selected}; leaked['A']['theta']=.01
            with self.assertRaises(ValueError): run.call_gate(leaked,method,phys)
            with self.assertRaises(ValueError): run.call_gate(selected,method,dict(phys,latent=0))
        with patch.object(run,'projection_evaluate',return_value={'decision':'ALLOW','reason':'arithmetic_failure'}):
            with self.assertRaises(ValueError): run.call_gate(counts,'projection_three',phys)
        with patch.object(run,'projection_evaluate',return_value={'decision':'ALLOW','reason':'projection_unresolved','projections':{}}):
            with self.assertRaises(ValueError): run.call_gate(counts,'projection_three',phys)

    def test_suppression_cannot_enter_observations(self):
        # First user accepts p, so natural path never exposes second r.
        for idx,(first,second,urgent) in enumerate(run.CATEGORIES):
            if first != 0: continue
            one=[0]*12; one[idx]=1
            natural=run.ledger(fixed_world(),'AB',4,one,'natural')
            forced=run.ledger(fixed_world(),'AB',4,one,'forced')
            self.assertEqual(natural['observed']['B']['r'],[0,0])
            self.assertEqual(natural['suppressed'],1)
            self.assertEqual(forced['observed']['B']['r'],[second,1])

    def test_seed_namespaces_are_fresh_and_keyed(self):
        self.assertEqual((run.SEED,run.BOOT_SEED),(71960431,71960432))
        self.assertNotIn(run.SEED,(55821761,55821762,94613011,94613012,83269021,83269022))
        keys=[]
        class Stub:
            def multinomial(self,n,p): return [n]+[0]*11
        def fake(key): keys.append(tuple(key)); return Stub()
        with patch.object(run,'rng',side_effect=fake):
            run.cells_for(fixed_world(),'AB',3,[run.SEED,1,0,0,0,0])
            run.cells_for(fixed_world(),'AB',3,[run.SEED,2,0,0,0,0])
        self.assertEqual(len(set(keys)),2)
        self.assertTrue(all(k[0]==run.SEED for k in keys))

    def test_matched_histories_latching_and_remaining_calendar(self):
        w=fixed_world(); w.update(name='fixture',benefit=.01,unmet=.003,truth_eligible=True)
        calls=[]
        def cells_stub(world, role, count, key): return [count]+[0]*11
        def gate_stub(counts,method,physics):
            calls.append((method,json.loads(json.dumps(counts))))
            return {'decision':'ALLOW' if len(calls)<=6 else 'ABSTAIN','reason':'fixture'}
        with patch.object(run,'CHECKPOINTS',(6,12)), patch.object(run,'world',return_value=w), \
             patch.object(run,'cells_for',side_effect=cells_stub), patch.object(run,'call_gate',side_effect=gate_stub):
            rows=run.rows_for_pair(0,0)
        self.assertEqual(len(rows),2)
        for block in (calls[:3],calls[3:6],calls[6:9],calls[9:12]):
            self.assertEqual(block[1][1],block[2][1])
            for user in ('A','B'):
                self.assertEqual(block[0][1][user],{k:v for k,v in block[1][1][user].items() if k!='third'})
        for schedule in run.SCHEDULES:
            for method in run.DATA_METHODS:
                name=schedule+'_'+method; earlier,later=rows[0]['methods'][name],rows[1]['methods'][name]
                self.assertEqual(earlier['first_crossing'],6)
                self.assertEqual(later['first_crossing'],6)
                self.assertEqual(later['raw']['decision'],'ABSTAIN')
                self.assertTrue(later['certified'])
                cur=rows[1]['totals'][schedule]; snap=rows[0]['totals'][schedule]
                deployment=rows[1]['deployment_evaluator_only']['ledger']
                self.assertAlmostEqual(later['stop_lifecycle_gain'],snap['gain']+cur['candidate_gain']-snap['candidate_gain']+deployment['candidate_gain'])
                self.assertAlmostEqual(later['stop_lifecycle_expected_unmet'],snap['expected_unmet']+cur['candidate_expected_unmet']-snap['candidate_expected_unmet']+deployment['candidate_expected_unmet'])
                self.assertAlmostEqual(later['lifecycle_gain'],cur['gain']+deployment['candidate_gain'])

    def test_hash_chain_manifest_and_receipt_fail_closed(self):
        first=run.chain_record('00'*32,{'x':1}); second=run.chain_record(first['sha256'],{'x':2})
        self.assertNotEqual(second['sha256'],run.chain_record(first['sha256'],{'x':3})['sha256'])
        self.assertNotEqual(second['sha256'],run.chain_record('00'*32,{'x':2})['sha256'])
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)
            bad=out/'manifest.json'; bad.write_text(json.dumps({'sha256':{}}))
            with self.assertRaises(ValueError): run.sources(bad)
            with self.assertRaises(TimeoutError): run.finish_receipt(out,{'status':'complete'},time.monotonic()-601)
            self.assertFalse((out/'completed.json').exists())

    def test_manifest_integrity_and_exclusive_output_before_rng(self):
        manifest={'sha256':{name:run.digest(run.ROOT/name) for name in run.REQUIRED}}
        with tempfile.TemporaryDirectory() as directory:
            out=Path(directory)
            path=out/'manifest.json'; path.write_text(json.dumps(manifest))
            self.assertEqual(run.sources(path),manifest['sha256'])
            first=next(iter(manifest['sha256'])); manifest['sha256'][first]='0'*64
            path.write_text(json.dumps(manifest))
            with self.assertRaises(ValueError): run.sources(path)
            # An existing output directory is rejected before any world or
            # event draw, even if source verification has been stubbed valid.
            with patch('sys.argv',['run','--manifest',str(path),'--out',str(out)]), \
                 patch.object(run,'sources',return_value={}), patch.object(run.signal,'alarm'), \
                 patch.object(run.signal,'signal'), patch.object(run,'world') as world:
                with self.assertRaises(FileExistsError): run.main()
                world.assert_not_called()


if __name__=='__main__': unittest.main()
