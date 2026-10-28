"""Verify six saved study hash chains without generating scientific data."""
import hashlib
import json
from pathlib import Path
import verify_research_package_five_studies_20261027 as five

ROOT=Path(__file__).resolve().parent.parent
STUDY=ROOT/'personalized_charging/projection_comparison_study_v2'

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def check(base,name,expected):
    path=Path(name)
    if path.is_absolute() or '..' in path.parts:raise ValueError('unsafe path')
    path=base/path
    if not path.is_file() or digest(path)!=expected:raise ValueError('missing or mismatched file: '+str(path))

def main():
    five.main()
    manifest=STUDY/'freeze_manifest.json'
    mapping=json.loads(manifest.read_text())['sha256']
    for name,sha in mapping.items():check(ROOT,name,sha)
    out=STUDY/'runs/heldout_20261028_v2'
    done=json.loads((out/'completed.json').read_text())
    if done.get('status')!='complete' or done.get('manifest_sha256')!=digest(manifest):
        raise ValueError('sixth completion or manifest mismatch')
    if done.get('source_sha256')!=mapping or done.get('row_count')!=3240:
        raise ValueError('sixth source identity or row count mismatch')
    expected={'started.json','checkpoints.jsonl','summary.json'}
    if set(done.get('output_sha256',{}))!=expected:raise ValueError('sixth output inventory mismatch')
    for name,sha in done['output_sha256'].items():check(out,name,sha)
    previous='00'*32;n=0
    with (out/'checkpoints.jsonl').open() as stream:
        for line in stream:
            item=json.loads(line)
            body=json.dumps(item['row'],sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
            current=hashlib.sha256(bytes.fromhex(previous)+body).hexdigest()
            if item['previous_sha256']!=previous or item['sha256']!=current:raise ValueError('sixth row hash chain mismatch')
            previous=current;n+=1
    if n!=3240 or previous!=done['chain_head']:raise ValueError('sixth chain head or length mismatch')
    print('Projection comparison source/completion/output and 3,240-row chain: OK')
    print('Hash checks do not prove a hermetic environment or empirical validity.')

if __name__=='__main__':main()
