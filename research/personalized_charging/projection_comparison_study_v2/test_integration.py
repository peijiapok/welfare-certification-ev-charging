"""Synthetic end-to-end controls; no scientific seed or sampled catalog."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from personalized_charging.projection_comparison_study_v2 import run
from personalized_charging.projection_comparison_study_v2.test_run import fixed_world


METHODS = tuple(s+'_'+m for s in run.SCHEDULES for m in run.DATA_METHODS)+('prior','default')


class BootstrapStub:
    def integers(self,low,high,size):
        if (low,high,size)==(0,4,(3,4)):
            return np.array([[0,0,0,0],[0,1,2,3],[3,3,3,3]])
        if (low,high,size)==(0,2,(3,2)):
            return np.array([[0,0],[0,1],[1,1]])
        raise AssertionError('unexpected bootstrap shape')


def synthetic_rows():
    rows=[]
    for pair in range(4):
        methods={}
        for i,m in enumerate(METHODS):
            gain=float((i+1)*(pair+1))
            methods[m]=dict(certified=(pair+i)%2==0,false_declaration=False,
                lifecycle_gain=gain,collection_gain=gain/2,lifecycle_unmet=float(pair),
                lifecycle_expected_unmet=float(pair)/10,stop_lifecycle_gain=-gain)
        w={'benefit':1. if pair<2 else -1.,'unmet':.004 if pair%2==0 else .006,
           'physics':{'epsilon':'.005'},'truth_eligible':pair==0}
        counts={s:{d:{o:[pair,pair+1] for o in run.OFFERS} for d in ('A','B')} for s in run.SCHEDULES}
        rows.append(dict(group='fixture',pair=pair,checkpoint=6,world_evaluator_only=w,
                         counts=counts,totals={'natural':{'suppressed':pair}},methods=methods))
    return rows


def expected_comparisons():
    pairs=[]
    for s in run.SCHEDULES:
        pairs.extend((s+'_'+a,s+'_'+b) for a,b in
                     (('two','three'),('two','projection_three'),('three','projection_three')))
        pairs.extend((s+'_'+m,base) for m in run.DATA_METHODS for base in ('prior','default'))
    pairs.extend(('natural_'+m,'forced_'+m) for m in run.DATA_METHODS)
    pairs.append(('prior','default'))
    return pairs


class EndToEndControls(unittest.TestCase):
    def test_all_summary_comparisons_and_bootstrap_known_answer(self):
        rows=synthetic_rows(); group=(('fixture',{},None,'fixture'),)
        with patch.object(run,'GROUPS',group), patch.object(run,'CHECKPOINTS',(6,)), \
             patch.object(run,'PAIRS',4), patch.object(run,'BOOTSTRAPS',3), \
             patch.object(run,'rng',return_value=BootstrapStub()) as rng:
            entry=run.summarize(rows)['fixture']['6']
        rng.assert_called_once_with([run.BOOT_SEED,0,0])
        self.assertEqual(set(entry['methods']),set(METHODS))
        self.assertEqual(set(entry['paired']),{a+'_minus_'+b for a,b in expected_comparisons()})
        self.assertEqual(len(entry['paired']),22)
        for a,b in expected_comparisons():
            record=entry['paired'][a+'_minus_'+b]
            delta=np.array([r['methods'][a]['lifecycle_gain']-r['methods'][b]['lifecycle_gain'] for r in rows])
            cert=np.array([int(r['methods'][a]['certified'])-int(r['methods'][b]['certified']) for r in rows])
            indices=np.array([[0,0,0,0],[0,1,2,3],[3,3,3,3]])
            self.assertAlmostEqual(record['mean'],float(np.mean(delta)))
            self.assertTrue(np.allclose(record['bootstrap_95'],np.quantile(delta[indices].mean(axis=1),[.025,.975])))
            self.assertTrue(np.allclose(record['certified_bootstrap_95'],np.quantile(cert[indices].mean(axis=1),[.025,.975])))
            self.assertTrue(np.allclose(record['stop_gain_bootstrap_95'],np.quantile(-delta[indices].mean(axis=1),[.025,.975])))
        for method in METHODS:
            self.assertEqual(sum(x['n'] for x in entry['methods'][method]['strata'].values()),4)
            self.assertTrue(all(x['n']==1 for x in entry['methods'][method]['strata'].values()))

    def run_fixture(self, directory, fail_summary=False):
        base=Path(directory); out=base/'exclusive_run'; manifest=base/'manifest.json'
        hashes={name:run.digest(run.ROOT/name) for name in run.REQUIRED}
        manifest.write_text(json.dumps({'sha256':hashes}))
        w=fixed_world(); w.update(name='fixture',benefit=.01,unmet=.003,truth_eligible=True)
        def cells_stub(world,role,count,key):
            if key[0]!=19990001: raise AssertionError('scientific seed reached fixture')
            return [count]+[0]*11
        def bootstrap_stub(key):
            if key[0]!=19990002: raise AssertionError('scientific bootstrap seed reached fixture')
            return BootstrapStub()
        group=(('fixture',w['physics'],None,'fixture'),)
        with patch('sys.argv',['run','--manifest',str(manifest),'--out',str(out)]), \
             patch.object(run,'GROUPS',group), patch.object(run,'PAIRS',2), \
             patch.object(run,'CHECKPOINTS',(6,12)), patch.object(run,'DEPLOYMENT',4), \
             patch.object(run,'BOOTSTRAPS',3), patch.object(run,'SEED',19990001), \
             patch.object(run,'BOOT_SEED',19990002), patch.object(run,'world',return_value=w), \
             patch.object(run,'cells_for',side_effect=cells_stub), patch.object(run,'rng',side_effect=bootstrap_stub), \
             patch.object(run.signal,'alarm'), patch.object(run.signal,'signal'), contextlib.redirect_stdout(io.StringIO()):
            if fail_summary:
                with patch.object(run,'summarize',side_effect=KeyError('synthetic summary failure')):
                    with self.assertRaises(KeyError): run.main()
            else:
                run.main()
        return out,manifest

    def test_miniature_output_hash_chain_and_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            out,manifest=self.run_fixture(directory)
            receipt=json.loads((out/'completed.json').read_text())
            self.assertEqual(receipt['status'],'complete')
            self.assertEqual(receipt['manifest_sha256'],run.digest(manifest))
            self.assertEqual(receipt['row_count'],4)
            self.assertEqual(set(receipt['output_sha256']),{'started.json','checkpoints.jsonl','summary.json'})
            for name,expected in receipt['output_sha256'].items():
                self.assertEqual(run.digest(out/name),expected)
            chain='00'*32
            for line in (out/'checkpoints.jsonl').read_text().splitlines():
                item=json.loads(line); self.assertEqual(item['previous_sha256'],chain)
                self.assertEqual(run.chain_record(chain,item['row']),item)
                chain=item['sha256']
            self.assertEqual(receipt['chain_head'],chain)
            summary=json.loads((out/'summary.json').read_text())['fixture']
            self.assertEqual(set(summary),{'6','12'})
            self.assertEqual(len(summary['12']['paired']),22)

    def test_summary_error_leaves_no_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            out,_=self.run_fixture(directory,fail_summary=True)
            self.assertTrue((out/'started.json').exists())
            self.assertTrue((out/'checkpoints.jsonl').exists())
            self.assertFalse((out/'completed.json').exists())


if __name__=='__main__': unittest.main()
