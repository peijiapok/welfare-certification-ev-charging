#!/usr/bin/env python3
"""Redraw the four manuscript figures from the saved summaries only.

The original plotting scripts run in temporary isolated directories. Existing
manuscript figures and historical research files are never modified.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parent
RUN='heldout_20261027_v1'
SPECS=(('figure_1','decision_outcomes'),('figure_2','matched_decisions'),
       ('figure_3','bias_robust_decisions'),('figure_4','prior_vs_collect'))

def digest(path):
    sha=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):sha.update(block)
    return sha.hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'regenerated_figures',
                        help='new output directory (must not already exist)')
    args=parser.parse_args(); out=args.output.expanduser().resolve()
    if out.exists():raise SystemExit('Output already exists; choose a new directory: '+str(out))
    manifest=json.loads((ROOT/'figure_provenance.json').read_text())
    for name,expected in manifest['file_sha256'].items():
        if not name.startswith(('figure_scripts/', 'figure_data/')):
            continue
        path=ROOT/name
        if not path.is_file() or digest(path)!=expected:
            raise SystemExit('Missing or modified figure source: '+str(path))
    with tempfile.TemporaryDirectory(prefix='charging-figure-reproduction-') as temporary:
        stage=Path(temporary); outputs=[]
        for label,stem in SPECS:
            work=stage/label; run=work/'runs'/RUN
            run.mkdir(parents=True)
            shutil.copy2(ROOT/'figure_scripts'/(label+'_plot.py'),work/'plot_results.py')
            for name in ('summary.json','completed.json'):
                source=ROOT/'figure_data'/label/name
                if source.exists():shutil.copy2(source,run/name)
            env=dict(os.environ, MPLBACKEND='Agg')
            result=subprocess.run([sys.executable,str(work/'plot_results.py')],cwd=work,env=env,
                                  text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            if result.returncode:
                raise RuntimeError(label+' plot failed:\n'+result.stdout+result.stderr)
            for ext in ('png','pdf','svg'):
                rendered=work/'figures'/(stem+'.'+ext)
                if not rendered.is_file():raise RuntimeError('Missing plot output '+str(rendered))
                outputs.append(rendered)
            print(label+': rendered '+stem+' (PNG, PDF, SVG)')
        out.mkdir(parents=True,exist_ok=False)
        for file in outputs:shutil.copy2(file,out/file.name)
    print('Saved regenerated figures in',out)
    print('No scientific simulations or historical outputs were changed.')

if __name__=='__main__':main()
