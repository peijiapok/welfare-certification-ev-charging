"""Check sealed study digests without generating new scientific data."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent.parent
FIRST = ROOT / "personalized_charging/sequential_identification_v1"
SECOND = ROOT / "personalized_charging/matched_verifiers_v1"
THIRD = ROOT / "personalized_charging/bias_robust_study_v1"
FOURTH = ROOT / "personalized_charging/variable_sensitivity_study_v1"


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def check(base, relative, expected):
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("unsafe manifest path")
    path = base / relative
    if not path.is_file() or digest(path) != expected:
        raise ValueError("missing or mismatched file: " + str(path))


def main():
    first_manifest = json.loads((FIRST / "freeze_manifest.json").read_text())
    for name, expected in first_manifest["sha256"].items():
        check(FIRST, name, expected)
    first_run = FIRST / "runs/heldout_20261027_v1"
    for line in (first_run / "SHA256SUMS").read_text().splitlines():
        value, name = line.split(None, 1)
        check(first_run, name.strip(), value)
    matched_manifest = SECOND / "freeze_manifest.json"
    for name, expected in json.loads(matched_manifest.read_text())["sha256"].items():
        check(ROOT, name, expected)
    matched_run = SECOND / "runs/heldout_20261027_v1"
    completed = json.loads((matched_run / "completed.json").read_text())
    if completed["status"] != "complete" or completed["manifest_sha256"] != digest(matched_manifest):
        raise ValueError("matched run completion/manifest mismatch")
    hashes = matched_run / "output_hashes.json"
    if completed["output_hashes_sha256"] != digest(hashes):
        raise ValueError("matched output hash index mismatch")
    entries = json.loads(hashes.read_text())["sha256"]
    for name, expected in entries.items():
        check(matched_run, name, expected)
    third_manifest = THIRD / "freeze_manifest.json"
    for name, expected in json.loads(third_manifest.read_text())["sha256"].items():
        check(ROOT, name, expected)
    third_run = THIRD / "runs/heldout_20261027_v1"
    third_completed = json.loads((third_run / "completed.json").read_text())
    if third_completed["status"] != "complete" or third_completed["manifest_sha256"] != digest(third_manifest):
        raise ValueError("finite-data run completion/manifest mismatch")
    third_hashes = third_run / "output_hashes.json"
    if third_completed["output_hashes_sha256"] != digest(third_hashes):
        raise ValueError("finite-data output hash index mismatch")
    third_entries = json.loads(third_hashes.read_text())["sha256"]
    for name, expected in third_entries.items():
        check(third_run, name, expected)
    fourth_manifest = FOURTH / "freeze_manifest.json"
    for name, expected in json.loads(fourth_manifest.read_text())["sha256"].items():
        check(ROOT, name, expected)
    fourth_run = FOURTH / "runs/heldout_20261027_v1"
    fourth_completed = json.loads((fourth_run / "completed.json").read_text())
    if fourth_completed["status"] != "complete" or fourth_completed["manifest_sha256"] != digest(fourth_manifest):
        raise ValueError("sensitivity run completion/manifest mismatch")
    fourth_hashes = fourth_run / "output_hashes.json"
    if fourth_completed["output_hashes_sha256"] != digest(fourth_hashes):
        raise ValueError("sensitivity output hash index mismatch")
    fourth_entries = json.loads(fourth_hashes.read_text())["sha256"]
    for name, expected in fourth_entries.items():
        check(fourth_run, name, expected)
    print("First study source/artifact hashes: OK")
    print(f"Matched study source/completion/artifact hashes: OK ({len(entries)} artifacts)")
    print(f"Finite-data study source/completion/artifact hashes: OK ({len(third_entries)} artifacts)")
    print(f"Sensitivity study source/completion/artifact hashes: OK ({len(fourth_entries)} artifacts)")
    print("Hash checks do not prove a hermetic environment or empirical validity.")


if __name__ == "__main__":
    main()
