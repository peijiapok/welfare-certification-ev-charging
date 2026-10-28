"""Verify the five sealed studies without generating new scientific data."""
from pathlib import Path
import hashlib
import json
import verify_research_package_20261027 as four_studies

ROOT=Path(__file__).resolve().parent.parent
FIFTH=ROOT/'personalized_charging/two_driver_study_v1'

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def check(base,name,expected):
    p=Path(name)
    if p.is_absolute() or '..' in p.parts: raise ValueError('unsafe hash path')
    target=base/p
    if not target.is_file() or digest(target)!=expected: raise ValueError('missing or mismatched file: '+str(target))

def main():
    four_studies.main()
    manifest=FIFTH/'freeze_manifest.json'
    mapping=json.loads(manifest.read_text())['sha256']
    for name,expected in mapping.items(): check(ROOT,name,expected)
    output=FIFTH/'runs/heldout_20261027_v1'
    done=json.loads((output/'completed.json').read_text())
    if done.get('status')!='complete' or done.get('manifest_sha256')!=digest(manifest):
        raise ValueError('two-driver completion or manifest mismatch')
    if done.get('source_sha256')!=mapping or done.get('row_count')!=3780:
        raise ValueError('two-driver source identity or row count mismatch')
    expected_outputs={'started.json','checkpoints.jsonl','summary.json'}
    if set(done.get('output_sha256',{}))!=expected_outputs:
        raise ValueError('two-driver output list mismatch')
    for name,expected in done['output_sha256'].items(): check(output,name,expected)
    print('Two-driver study source/completion/artifact hashes: OK (3 artifacts)')
    print('These checks do not establish independent arithmetic or empirical validity.')

if __name__=='__main__': main()
