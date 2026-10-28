"""Deterministic runner checks. These do not execute the held-out catalog."""
import csv
import io
import math
import unittest
from fractions import Fraction
from unittest.mock import patch

import numpy as np

from personalized_charging.sequential_identification_v1 import run
from personalized_charging.sequential_identification_v1.physical import simulate_episode


class RunnerTests(unittest.TestCase):
    def test_posterior_shape_normalization_and_bayesian_update(self):
        model = run.GridPosterior()
        self.assertEqual(model.weights().shape, (31 * 15,))
        self.assertAlmostEqual(float(model.weights().sum()), 1.)
        expected = model.p / model.p.sum()
        model.observe("p", True)
        np.testing.assert_allclose(model.weights(), expected, rtol=1e-14, atol=1e-16)
        for _ in range(200):
            model.observe("r", False)
        self.assertTrue(np.all(np.isfinite(model.weights())))
        self.assertAlmostEqual(float(model.weights().sum()), 1.)

    def test_public_decisions_and_ties(self):
        p = run.GridPosterior()
        self.assertEqual(p.choose("p_only", 1), "p")
        self.assertEqual([p.choose("alternating", i) for i in range(4)], ["p", "r", "p", "r"])
        with patch.object(p, "entropy_reduction", return_value=.1):
            self.assertEqual(p.choose("entropy", 0), "p")
        # The method signature itself limits the collector API to posterior and index.
        self.assertEqual(list(__import__('inspect').signature(p.choose).parameters),
                         ["collector", "episode_index"])
        with self.assertRaises(ValueError):
            p.observe("p", np.bool_(True))

    def test_true_benefit_matches_physical_enumeration_with_overrides(self):
        theta, p, r = .12, .83, .71
        actual_b, actual_u = run.actual_metrics(theta, p, r)
        total_b = total_u = 0.
        for hp, wp, up in ((True, p, p/2), (False, 1-p, (1+p)/2)):
            for hr, wr, ur in ((True, r, r/2), (False, 1-r, (1+r)/2)):
                for urgent, wu, uu in ((True, .005, 0.), (False, .995, .5)):
                    weight = wp * wr * wu
                    c = simulate_episode("candidate", theta, .2, up, ur, uu,
                                         p_response=p, r_response=r)
                    b = simulate_episode("baseline", theta, .2, up, ur, uu,
                                         p_response=p, r_response=r)
                    total_b += weight * (b.loss - c.loss)
                    total_u += weight * c.unmet_kwh
        self.assertAlmostEqual(actual_b, total_b)
        self.assertAlmostEqual(actual_u, total_u)
        self.assertNotEqual(actual_b, run.actual_metrics(theta, .5, .6)[0])

    def test_no_offer_is_not_a_response(self):
        baseline = simulate_episode("baseline", .1, .2, .1, .2, .3)
        self.assertEqual(run.visible_feedback(baseline), [])
        first_only = simulate_episode("collect_p", .1, .2, .1, .2, .3)
        self.assertEqual(run.visible_feedback(first_only), [("p", True)])

    def test_driver_common_innovations_ever_gate_and_strict_service(self):
        # All p probes accept. The gate crosses on the exact known-answer prefix,
        # while collection continues through the full cap for each rule.
        draws = np.full((20, 3), .99)
        draws[:, 0] = 0.
        rows, oracle = run.run_driver("easy", 7, 0., .05, Fraction(1, 200), False,
                                      draws, collection_episodes=16, deployment_episodes=4)
        self.assertEqual(len(rows), 8)
        p_exact = next(x for x in rows if x["collector"] == "p_only" and x["gate"] == "exact")
        self.assertEqual(p_exact["first_crossing"], 11)
        self.assertTrue(p_exact["deployed"])
        self.assertEqual((p_exact["p_samples"], p_exact["r_samples"]), (16, 0))
        self.assertTrue(p_exact["true_eligible"])
        self.assertAlmostEqual(p_exact["expected_collection_unmet"], 16 * p_exact["actual_p"] / 200)
        self.assertTrue(all(row["first_crossing"] is None and row["false_bound_declaration"] is None
                            for row in rows if row["gate"] == "plugin"))
        self.assertAlmostEqual(p_exact["oracle_deployment_benefit"], oracle)
        tight, _ = run.run_driver("tight_service", 7, 0., .05, Fraction(9, 2000), False,
                                  draws, collection_episodes=16, deployment_episodes=4)
        self.assertFalse(any(row["deployed"] for row in tight if row["gate"] == "exact"))
        self.assertTrue(all(row["first_crossing"] is None for row in tight))

    def test_actual_misspecification_and_absent_event_data(self):
        draws = np.array([[.7, .8, .1], [.3, .4, .002], [.4, .1, .5]], dtype=float)
        stream = io.StringIO()
        writer = csv.writer(stream)
        rows, _ = run.run_driver("misspecified", 0, .18, .1, Fraction(1, 200), True,
                                 draws, writer, collection_episodes=2, deployment_episodes=1)
        row = rows[0]
        p = 1 / (1 + math.exp(-((.1 - .18)/.1 + 2)))
        r = 1 / (1 + math.exp(-((.1 - .18/2)/.1 + 2)))
        self.assertAlmostEqual(row["actual_p"], p)
        self.assertAlmostEqual(row["actual_B"], run.actual_metrics(.18, p, r)[0])
        self.assertFalse(row["true_eligible"])
        for line in csv.reader(io.StringIO(stream.getvalue())):
            self.assertEqual(len(line), 12)
            # Event rows contain only fields needed for observable physical outcomes.
            self.assertNotIn(str(.18), line)
            self.assertNotIn(str(p), line)

    def test_reproducibility_and_small_paired_summary(self):
        generator = np.random.Generator(np.random.PCG64(91))
        draws = generator.random((6, 3))
        one, oracle = run.run_driver("easy", 0, .01, .06, Fraction(1, 200), False,
                                     draws, collection_episodes=4, deployment_episodes=2)
        two, _ = run.run_driver("easy", 0, .01, .06, Fraction(1, 200), False,
                                draws, collection_episodes=4, deployment_episodes=2)
        self.assertEqual(one, two)
        a = run.make_summary(one, {("easy", 0): oracle}, n_bootstrap=20)
        b = run.make_summary(one, {("easy", 0): oracle}, n_bootstrap=20)
        self.assertEqual(a, b)
        self.assertEqual(a["easy"]["methods"]["p_only:exact"]["n"], 1)
        self.assertEqual(run.wilson(0, 0), None)
        self.assertEqual(a["easy"]["paired_differences"]["p_only:exact minus default"]["n"], 1)
        self.assertTrue(all("oracle" not in k for k in a["easy"]["paired_differences"]))
        self.assertTrue(any("oracle_deployment_only" in k for k in a["easy"]["deployment_paired_differences"]))
        self.assertIsNone(a["easy"]["methods"]["p_only:plugin"]["ever_certified"])
        self.assertIsNone(a["easy"]["methods"]["p_only:plugin"]["bound_claim_false_n"])

    def test_manifest_validation_and_output_directory_protection(self):
        import json
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            hashes = run.source_hashes()
            manifest.write_text(json.dumps({"sha256": hashes}))
            digest, actual = run.verify_manifest(manifest)
            self.assertEqual(actual, hashes)
            self.assertEqual(len(digest), 64)
            with self.assertRaises(FileExistsError):
                run.main(["--manifest", str(manifest), "--output", directory])
            hashes["physical.py"] = "0" * 64
            manifest.write_text(json.dumps({"sha256": hashes}))
            fresh = root / "must_not_exist"
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                run.main(["--manifest", str(manifest), "--output", str(fresh)])
            self.assertFalse(fresh.exists())
            del hashes["physical.py"]
            manifest.write_text(json.dumps({"sha256": hashes}))
            with self.assertRaisesRegex(ValueError, "exactly the seven"):
                run.verify_manifest(manifest)

    def test_full_fixture_output_integrity_and_interrupted_status(self):
        import hashlib
        import json
        import tempfile
        from pathlib import Path
        fixture_groups = (("fixture", (.041, .041), (.17, .17), Fraction(1, 200), False),)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"sha256": run.source_hashes()}))
            with patch.object(run, "GROUPS", fixture_groups), \
                 patch.object(run, "DRIVERS_PER_GROUP", 1), \
                 patch.object(run, "MASTER_SEED", 99123):
                output = root / "complete"
                self.assertEqual(run.main(["--manifest", str(manifest), "--output", str(output)]), 0)
                summary = json.loads((output / "summary.json").read_text())
                self.assertEqual(summary["status"], "complete")
                self.assertEqual(summary["drivers_completed"], 1)
                self.assertEqual(summary["master_seed"], 99123)
                for line in (output / "SHA256SUMS").read_text().splitlines():
                    digest, name = line.split("  ")
                    self.assertEqual(digest, hashlib.sha256((output/name).read_bytes()).hexdigest())
                self.assertEqual(json.loads((output/"started.json").read_text())["status"], "started_incomplete")
                incomplete = root / "interrupted"
                with patch.object(run, "run_driver", side_effect=InterruptedError("fixture interrupt")):
                    with self.assertRaises(InterruptedError):
                        run.main(["--manifest", str(manifest), "--output", str(incomplete)])
                failed = json.loads((incomplete / "summary.json").read_text())
                self.assertEqual(failed["status"], "incomplete")
                self.assertEqual(failed["drivers_completed"], 0)
                self.assertTrue((incomplete / "SHA256SUMS").exists())


if __name__ == "__main__":
    unittest.main()
