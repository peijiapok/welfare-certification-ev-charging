"""Frozen-design sequential charging experiment runner.

This module does not run an experiment on import. Only observed events enter
collector decisions. The continuous true model and random innovations are
restricted to the simulator/evaluator. The grid posterior is a heuristic,
not a continuous-domain confidence set.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import os
import platform
import resource
import signal
import sys
import time
import traceback
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path

import numpy as np

from personalized_charging.sequential_identification_v1.certificate import PProbeCertificate
from personalized_charging.sequential_identification_v1.physical import simulate_episode

MASTER_SEED = 730411
BOOTSTRAP_SEED = 730412
DRIVERS_PER_GROUP = 300
COLLECTION_EPISODES = 64
DEPLOYMENT_EPISODES = 32
BOOTSTRAP_REPLICATES = 2000
TIME_LIMIT_SECONDS = 600
COLLECTORS = ("p_only", "alternating", "entropy", "myopic")
GATES = ("exact", "plugin")
GROUPS = (
    ("easy", (0., .02), (.05, .08), Fraction(1, 200), False),
    ("low_information_positive", (0., .035), (.2, .4), Fraction(1, 200), False),
    ("boundary", (.055, .10), (.05, .25), Fraction(1, 200), False),
    ("harmful", (.11, .25), (.05, .4), Fraction(1, 200), False),
    ("tight_service", (0., .10), (.05, .2), Fraction(9, 2000), False),
    ("misspecified", (.11, .20), (.05, .2), Fraction(1, 200), True),
)


def sigmoid(x):
    return 1. / (1. + np.exp(-np.asarray(x)))


def actual_metrics(theta, p, r):
    """Actual candidate benefit and expected unmet using actual responses."""
    return (p * (.07 - theta) + (1 - p) * r * (.05 - theta / 2),
            (p + (1 - p) * r) / 200.)


class GridPosterior:
    """Uniform 31 x 15 model grid; decisions use only past public feedback."""
    def __init__(self):
        theta, tau = np.meshgrid(np.linspace(0., .25, 31),
                                 np.linspace(.05, .4, 15), indexing="ij")
        self.theta = theta.ravel()
        self.tau = tau.ravel()
        self.p = sigmoid((.1 - self.theta) / self.tau)
        self.r = sigmoid((.1 - self.theta / 2.) / self.tau)
        self.b, self.u = actual_metrics(self.theta, self.p, self.r)
        self.log_weight = np.full(self.theta.size, -math.log(self.theta.size))

    def weights(self):
        # Recenter before exponentiation and renormalize after every update.
        w = np.exp(self.log_weight - np.max(self.log_weight))
        return w / np.sum(w)

    def observe(self, offer, accepted):
        if offer not in ("p", "r") or type(accepted) is not bool:
            raise ValueError("one observed offer and boolean response required")
        probability = self.p if offer == "p" else self.r
        self.log_weight += np.log(probability) if accepted else np.log1p(-probability)
        self.log_weight -= np.max(self.log_weight)

    @staticmethod
    def binary_entropy(probability):
        if probability <= 0. or probability >= 1.:
            return 0.
        return -probability * math.log(probability) - (1. - probability) * math.log1p(-probability)

    def entropy_reduction(self, offer):
        w = self.weights()
        q = self.p if offer == "p" else self.r
        positive = self.b > 0.
        prior = self.binary_entropy(float(np.sum(w[positive])))
        accept = float(np.dot(w, q))
        pos_accept = float(np.dot(w[positive], q[positive]))
        pos_reject = float(np.dot(w[positive], 1. - q[positive]))
        posterior = 0.
        if accept > 0.:
            posterior += accept * self.binary_entropy(pos_accept / accept)
        if accept < 1.:
            posterior += (1. - accept) * self.binary_entropy(pos_reject / (1. - accept))
        return prior - posterior

    def choose(self, collector, episode_index):
        if collector == "p_only":
            return "p"
        if collector == "alternating":
            return "p" if episode_index % 2 == 0 else "r"
        if collector == "entropy":
            p_score, r_score = self.entropy_reduction("p"), self.entropy_reduction("r")
        elif collector == "myopic":
            w = self.weights()
            p_score = float(np.dot(w, self.p * (.07 - self.theta)))
            r_score = float(np.dot(w, self.r * (.05 - self.theta / 2.)))
        else:
            raise ValueError("unknown collector")
        return "p" if p_score >= r_score else "r"

    def plugin(self, epsilon):
        w = self.weights()
        return bool(np.dot(w, self.b) > 0. and np.dot(w, self.u) <= float(epsilon))


def visible_feedback(episode):
    return [(e.offer, e.accepted) for e in episode.events if e.offer is not None]


def log_episode(writer, group, driver, arm, phase, episode_index, episode):
    if writer is None:
        return
    for event in episode.events:
        writer.writerow((group, driver, arm, phase, episode_index, event.request,
                         event.offer or "", "" if event.accepted is None else int(event.accepted),
                         "" if event.assigned_slot is None else event.assigned_slot,
                         *(int(x) for x in event.occupied_after)))


def run_driver(group, driver, theta, tau, epsilon, misspecified, innovations,
               event_writer=None, collection_episodes=COLLECTION_EPISODES,
               deployment_episodes=DEPLOYMENT_EPISODES):
    """One independent driver/world; use only for evaluation, never a policy."""
    if innovations.shape != (collection_episodes + deployment_episodes, 3):
        raise ValueError("innovations must contain independent p, r and urgent draws per episode")
    shift = 2. if misspecified else 0.
    nominal_p = float(sigmoid((.1 - theta) / tau))
    p = float(sigmoid((.1 - theta) / tau + shift))
    r = float(sigmoid((.1 - theta / 2.) / tau + shift))
    benefit, service = actual_metrics(theta, p, r)
    eligible = bool(benefit > 0. and service <= float(epsilon))

    def episode(policy, i):
        # Explicit built-in floats keep physical comparisons and event booleans stable.
        up, ur, uu = (float(x) for x in innovations[i])
        return simulate_episode(policy, float(theta), float(tau), up, ur, uu,
                                p_response=p, r_response=r)

    defaults = [episode("baseline", i) for i in range(len(innovations))]
    deployment = [episode("candidate", i) for i in range(collection_episodes, len(innovations))]
    records = []
    for collector in COLLECTORS:
        posterior, certificate = GridPosterior(), PProbeCertificate()
        crossing = None
        collection_benefit, collection_loss, collection_unmet = 0., 0., 0.
        expected_collection_unmet = 0.
        p_samples = r_samples = 0
        choice_sequence = []
        for i in range(collection_episodes):
            # No simulator parameter, response probability, or current innovation is
            # passed into this call: only posterior and the public episode index.
            choice = posterior.choose(collector, i)
            choice_sequence.append(choice)
            result = episode("collect_" + choice, i)
            feedback = visible_feedback(result)
            if len(feedback) != 1 or feedback[0][0] != choice:
                raise RuntimeError("collector received unexpected physical feedback")
            offer, accepted = feedback[0]
            posterior.observe(offer, accepted)
            certificate.observe(offer, accepted)
            p_samples += int(offer == "p")
            r_samples += int(offer == "r")
            if crossing is None and certificate.evaluate(epsilon).certified:
                crossing = i + 1
            collection_benefit += defaults[i].loss - result.loss
            collection_loss += result.loss
            collection_unmet += result.unmet_kwh
            expected_collection_unmet += (p if choice == "p" else r) / 200.
            log_episode(event_writer, group, driver, collector, "collection", i, result)
        decisions = {"exact": crossing is not None, "plugin": posterior.plugin(epsilon)}
        for gate, deploy in decisions.items():
            deployment_benefit, deployment_unmet = 0., 0.
            for j, candidate in enumerate(deployment):
                i = collection_episodes + j
                result = candidate if deploy else defaults[i]
                deployment_benefit += defaults[i].loss - result.loss
                deployment_unmet += result.unmet_kwh
                log_episode(event_writer, group, driver, collector + ":" + gate,
                            "deployment", j, result)
            records.append(dict(group=group, driver=driver, collector=collector, gate=gate,
                                theta=theta, tau=tau, actual_p=p, actual_r=r,
                                epsilon=float(epsilon), actual_B=benefit, actual_U=service,
                                nominal_p=nominal_p, model_misspecified=misspecified,
                                actual_p_null=bool(p <= 2/3),
                                nominal_p_null=bool(nominal_p <= 2/3),
                                actual_bound_null=bool(benefit <= float(Fraction(161, 41100))),
                                true_eligible=eligible, first_crossing=crossing if gate == "exact" else None,
                                p_samples=p_samples, r_samples=r_samples,
                                choices="".join(choice_sequence), deployed=deploy,
                                false_declaration=bool(deploy and not eligible),
                                false_bound_declaration=bool(deploy and benefit <= float(Fraction(161, 41100))) if gate == "exact" else None,
                                false_p_null_declaration=bool(deploy and p <= 2/3) if gate == "exact" else None,
                                nominal_p_null_diagnostic=bool(deploy and nominal_p <= 2/3) if gate == "exact" else None,
                                collection_loss=collection_loss, collection_benefit=collection_benefit,
                                collection_unmet=collection_unmet,
                                expected_collection_unmet=expected_collection_unmet,
                                deployment_benefit=deployment_benefit,
                                deployment_unmet=deployment_unmet,
                                lifecycle_benefit=collection_benefit + deployment_benefit,
                                expected_deployment_unmet=service if deploy else 0.))
    oracle_benefit = sum(defaults[collection_episodes + j].loss - x.loss
                         for j, x in enumerate(deployment)) if eligible else 0.
    # Oracle has no collection cost; same 32-deployment horizon as the arms.
    for record in records:
        record["oracle_deployment_benefit"] = oracle_benefit
    return records, oracle_benefit


def wilson(successes, total):
    if not total:
        return None
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z*z / total
    center = (p + z*z / (2*total)) / denominator
    radius = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total)) / denominator
    return [max(0., center-radius), min(1., center+radius)]


def make_summary(rows, oracles, bootstrap_seed=BOOTSTRAP_SEED,
                 n_bootstrap=BOOTSTRAP_REPLICATES):
    rng = np.random.Generator(np.random.PCG64(bootstrap_seed))
    result = {}
    for group, *_ in GROUPS:
        group_rows = [row for row in rows if row["group"] == group]
        if not group_rows:
            continue
        ids = sorted({row["driver"] for row in group_rows})
        by_key = {(row["driver"], row["collector"] + ":" + row["gate"]): row
                  for row in group_rows}
        methods = [f"{c}:{g}" for c in COLLECTORS for g in GATES]
        if any((driver, method) not in by_key for driver in ids for method in methods):
            raise ValueError("incomplete driver records")
        n = len(ids)
        values = {method: np.array([by_key[(driver, method)]["lifecycle_benefit"]
                                    for driver in ids], dtype=float) for method in methods}
        values["default"] = np.zeros(n)
        deployment_values = {method: np.array([by_key[(driver, method)]["deployment_benefit"]
                                               for driver in ids], dtype=float) for method in methods}
        deployment_values["default"] = np.zeros(n)
        deployment_values["oracle_deployment_only_non_deployable"] = np.array(
            [oracles[(group, driver)] for driver in ids])
        resamples = rng.integers(0, n, size=(n_bootstrap, n))
        metrics = {}
        for method in methods:
            m = [by_key[(driver, method)] for driver in ids]
            deployed = sum(row["deployed"] for row in m)
            ineligible = sum(not row["true_eligible"] for row in m)
            false = sum(row["deployed"] and not row["true_eligible"] for row in m)
            crossings = sum(row["first_crossing"] is not None for row in m)
            exact = m[0]["gate"] == "exact"
            bound_null_n = sum(row["actual_bound_null"] for row in m)
            p_null_n = sum(row["actual_p_null"] for row in m)
            nominal_null_n = sum(row["nominal_p_null"] for row in m)
            bound_false = sum(bool(row["false_bound_declaration"]) for row in m)
            p_false = sum(bool(row["false_p_null_declaration"]) for row in m)
            nominal_false = sum(bool(row["nominal_p_null_diagnostic"]) for row in m)
            metrics[method] = {
                "n": n, "deployed": deployed, "deployed_fraction": deployed/n,
                "deployed_wilson_95": wilson(deployed, n),
                "abstained": n-deployed, "abstention_fraction": (n-deployed)/n,
                "abstention_wilson_95": wilson(n-deployed, n),
                "ever_certified": crossings if exact else None,
                "ever_certified_fraction": crossings/n if exact else None,
                "ever_certified_wilson_95": wilson(crossings, n) if exact else None,
                "ineligible_n": ineligible, "false_declarations": false,
                "false_declaration_fraction_all": false/n,
                "false_declaration_wilson_95_all": wilson(false, n),
                "false_declaration_fraction_ineligible": false/ineligible if ineligible else None,
                "false_declaration_wilson_95_ineligible": wilson(false, ineligible),
                "bound_claim_null_n": bound_null_n,
                "bound_claim_false_n": bound_false if exact else None,
                "bound_claim_false_fraction_null": bound_false/bound_null_n if exact and bound_null_n else None,
                "bound_claim_false_wilson_95_null": wilson(bound_false, bound_null_n) if exact else None,
                "actual_p_null_n": p_null_n,
                "actual_p_null_rejections": p_false if exact else None,
                "actual_p_null_rejection_fraction": p_false/p_null_n if exact and p_null_n else None,
                "actual_p_null_rejection_wilson_95": wilson(p_false, p_null_n) if exact else None,
                "nominal_p_null_n": nominal_null_n,
                "nominal_p_null_rejections": nominal_false if exact else None,
                "nominal_p_null_rejection_fraction": nominal_false/nominal_null_n if exact and nominal_null_n else None,
                "nominal_p_null_rejection_wilson_95": wilson(nominal_false, nominal_null_n) if exact else None,
                "nominal_p_null_interpretation": "diagnostic_only_under_misspecification" if group == "misspecified" else "nominal_model",
                "mean_lifecycle_benefit": float(np.mean(values[method])),
                "mean_collection_loss": float(np.mean([r["collection_loss"] for r in m])),
                "mean_collection_benefit": float(np.mean([r["collection_benefit"] for r in m])),
                "mean_collection_unmet": float(np.mean([r["collection_unmet"] for r in m])),
                "mean_expected_collection_unmet": float(np.mean([r["expected_collection_unmet"] for r in m])),
                "mean_deployment_unmet": float(np.mean([r["deployment_unmet"] for r in m])),
                "mean_expected_deployment_unmet": float(np.mean([r["expected_deployment_unmet"] for r in m])),
                "mean_p_samples": float(np.mean([r["p_samples"] for r in m])),
                "mean_r_samples": float(np.mean([r["r_samples"] for r in m])),
                "first_crossings": [r["first_crossing"] for r in m if r["first_crossing"] is not None],
            }
        paired = {}
        keys = list(values)
        for i, a in enumerate(keys):
            for b in keys[i+1:]:
                delta = values[a] - values[b]
                draws = np.mean(delta[resamples], axis=1)
                paired[a + " minus " + b] = {
                    "n": n, "mean": float(np.mean(delta)),
                    "bootstrap_95": [float(x) for x in np.quantile(draws, [.025, .975])],
                }
        deployment_paired = {}
        keys = list(deployment_values)
        for i, a in enumerate(keys):
            for b in keys[i+1:]:
                delta = deployment_values[a] - deployment_values[b]
                draws = np.mean(delta[resamples], axis=1)
                deployment_paired[a + " minus " + b] = {
                    "n": n, "mean": float(np.mean(delta)),
                    "bootstrap_95": [float(x) for x in np.quantile(draws, [.025, .975])],
                }
        result[group] = {"n": n, "methods": metrics, "paired_differences": paired,
                         "deployment_paired_differences": deployment_paired,
                         "oracle_mean_deployment_benefit": float(np.mean(deployment_values["oracle_deployment_only_non_deployable"]))}
    return result


def source_hashes():
    directory = Path(__file__).resolve().parent
    names = ("PROTOCOL.md", "run.py", "physical.py", "certificate.py",
             "test_run.py", "test_physical.py", "test_certificate.py")
    return {name: hashlib.sha256((directory/name).read_bytes()).hexdigest() for name in names}


def verify_manifest(path):
    """Verify exactly the seven fixed files before generating any data."""
    raw = Path(path).read_bytes()
    manifest = json.loads(raw)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("sha256"), dict):
        raise ValueError("manifest must contain a sha256 mapping")
    expected = manifest["sha256"]
    actual = source_hashes()
    if set(expected) != set(actual):
        raise ValueError("manifest must list exactly the seven required source and protocol files")
    if any(not isinstance(value, str) or len(value) != 64 or
           any(c not in "0123456789abcdef" for c in value) for value in expected.values()):
        raise ValueError("manifest SHA-256 values must be lowercase hexadecimal digests")
    mismatch = [name for name in actual if actual[name] != expected[name]]
    if mismatch:
        raise ValueError("manifest digest mismatch: " + ", ".join(mismatch))
    return hashlib.sha256(raw).hexdigest(), actual


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="new output directory; must not already exist")
    parser.add_argument("--manifest", type=Path, required=True, help="JSON freeze manifest with the seven fixed SHA-256 digests")
    args = parser.parse_args(argv)
    manifest_digest, verified_hashes = verify_manifest(args.manifest)
    out = args.output or Path("sequential_identification_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ"))
    out.mkdir(exist_ok=False)
    start = time.monotonic()
    (out / "started.json").write_text(json.dumps({"status": "started_incomplete", "manifest_sha256": manifest_digest}) + "\n", encoding="utf-8")
    previous_sigterm = signal.getsignal(signal.SIGTERM)
    def interrupted(signum, frame):
        raise InterruptedError("SIGTERM received; run is incomplete and cannot be resumed")
    signal.signal(signal.SIGTERM, interrupted)
    metadata = {"status": "incomplete", "master_seed": MASTER_SEED,
                "bootstrap_seed": BOOTSTRAP_SEED, "python": sys.version,
                "platform": platform.platform(), "numpy": np.__version__,
                "bit_generator": "PCG64", "hashes_sha256": verified_hashes,
                "manifest_sha256": manifest_digest,
                "time_limit_seconds": TIME_LIMIT_SECONDS, "groups": {}}
    rows, oracles = [], {}
    rng = np.random.Generator(np.random.PCG64(MASTER_SEED))
    error = None
    try:
        with gzip.open(out/"events.csv.gz", "wt", newline="", encoding="utf-8") as stream:
            events = csv.writer(stream)
            events.writerow(("group", "driver", "arm", "phase", "episode", "request", "offer",
                             "accepted", "assigned_slot", "occupied_0", "occupied_1", "occupied_2"))
            for name, theta_range, tau_range, epsilon, misspecified in GROUPS:
                # One generator, fixed group order: parameter arrays then each independent
                # driver's full innovation tensor. Separate columns are separate draws.
                thetas = rng.uniform(*theta_range, DRIVERS_PER_GROUP)
                taus = rng.uniform(*tau_range, DRIVERS_PER_GROUP)
                for i in range(DRIVERS_PER_GROUP):
                    if time.monotonic() - start >= TIME_LIMIT_SECONDS:
                        raise TimeoutError("fixed run time limit reached; no extension")
                    draws = rng.random((COLLECTION_EPISODES + DEPLOYMENT_EPISODES, 3))
                    batch, oracle = run_driver(name, i, float(thetas[i]), float(taus[i]),
                                               epsilon, misspecified, draws, events)
                    rows.extend(batch)
                    oracles[(name, i)] = oracle
        metadata["groups"] = make_summary(rows, oracles)
        if time.monotonic() - start >= TIME_LIMIT_SECONDS:
            raise TimeoutError("fixed run time limit reached during analysis; no extension")
        if source_hashes() != verified_hashes:
            raise RuntimeError("source or protocol changed during the run")
        metadata["status"] = "complete"
    except BaseException as exc:
        error = exc
        metadata["error"] = {"type": type(exc).__name__, "message": str(exc),
                             "traceback": traceback.format_exc()}
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm)
        try:
            end_hashes = source_hashes()
            metadata["end_hashes_sha256"] = end_hashes
            if end_hashes != verified_hashes:
                metadata["status"] = "incomplete"
                if error is None:
                    error = RuntimeError("source or protocol changed during the run")
                    metadata["error"] = {"type": type(error).__name__, "message": str(error)}
        except Exception as exc:
            metadata["status"] = "incomplete"
            if error is None:
                error = exc
                metadata["error"] = {"type": type(exc).__name__, "message": str(exc)}
        if rows:
            with (out/"drivers.csv").open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
        metadata["drivers_completed"] = len(oracles)
        metadata["artifacts_sha256"] = {}
        for name in ("started.json", "drivers.csv", "events.csv.gz"):
            path = out / name
            if path.exists():
                h = hashlib.sha256()
                with path.open("rb") as artifact:
                    for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
                        h.update(chunk)
                metadata["artifacts_sha256"][name] = h.hexdigest()
        metadata["elapsed_seconds"] = time.monotonic() - start
        usage = resource.getrusage(resource.RUSAGE_SELF)
        metadata["cpu_user_seconds"] = usage.ru_utime
        metadata["cpu_system_seconds"] = usage.ru_stime
        metadata["max_rss_platform_units"] = usage.ru_maxrss
        with (out/"summary.json").open("w", encoding="utf-8") as stream:
            json.dump(metadata, stream, indent=2, allow_nan=False)
            stream.write("\n")
        artifact_names = ["started.json", "drivers.csv", "events.csv.gz", "summary.json"]
        with (out / "SHA256SUMS").open("w", encoding="utf-8") as stream:
            for name in artifact_names:
                path = out / name
                if path.exists():
                    h = hashlib.sha256()
                    with path.open("rb") as artifact:
                        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
                            h.update(chunk)
                    stream.write(f"{h.hexdigest()}  {name}\n")
    if error is not None:
        raise error
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
