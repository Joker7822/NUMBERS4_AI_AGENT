from datetime import date, timedelta
import unittest

from numbers4_agent import stability_audit as s


def fixture(n=240):
    return [{"round": i+2, "data_cutoff_round": i+1,
             "draw_date": (date(2020, 1, 1)+timedelta(days=i)).isoformat(),
             **{key: (j+1)*((i%7)-3)/100 for j, key in enumerate(s.SERIES)}}
            for i in range(n)]


class StabilityAuditTests(unittest.TestCase):
    def test_constant_and_zero_scores(self):
        series = {k: [float(i)]*103 for i,k in enumerate(s.SERIES)}
        report = s.resample(series, block_length=20, replicates=100, seed=4)
        for i,k in enumerate(s.SERIES):
            self.assertEqual(report[k]["nominal_95_percent_resampling_range"], [i,i])
            self.assertEqual(report[k]["nominal_bonferroni_percentile_range"], [i,i])
            self.assertEqual(report[k]["adjusted_lower_above_zero_descriptive"], i>0)

    def test_wraparound_and_partial_block(self):
        self.assertEqual(s._circular_sums([1,2,3,4],3), [6,9,8,7])
        series = {key: [1.,2.,3.,4.,5.] for key in s.SERIES}
        result = s.resample(series, block_length=3, replicates=100, seed=1)
        self.assertEqual(len(result),4)
        self.assertEqual(result[s.SERIES[0]], result[s.SERIES[-1]])

    def test_reproducible_and_adjustment_never_narrows(self):
        rows=fixture()
        a=s.evaluate(rows, split_round=121, replicates=100, seed=9)
        self.assertEqual(a,s.evaluate(rows, split_round=121, replicates=100, seed=9))
        self.assertEqual(a["within_audit_comparison_count"],24)
        self.assertFalse(a["confidence_coverage_guaranteed"])
        for cohort in a["cohorts"].values():
            for block in cohort["block_results"].values():
                for value in block.values():
                    low,high=value["nominal_95_percent_resampling_range"]
                    wider_low,wider_high=value["nominal_bonferroni_percentile_range"]
                    self.assertLessEqual(wider_low,low)
                    self.assertGreaterEqual(wider_high,high)

    def test_future_change_does_not_change_development_resampling(self):
        rows=fixture()
        a=s.evaluate(rows,split_round=121,replicates=100)
        rows[-1][s.SERIES[0]]=99.
        b=s.evaluate(rows,split_round=121,replicates=100)
        self.assertEqual(a["cohorts"]["development"],b["cohorts"]["development"])

    def test_reject_invalid_inputs_and_short_cohorts(self):
        rows=fixture()
        with self.assertRaises(ValueError):
            s.evaluate(rows,split_round=20,replicates=100)
        rows[-1]["data_cutoff_round"]=rows[-1]["round"]
        with self.assertRaises(ValueError):
            s.evaluate(rows,split_round=121,replicates=100)
        rows=fixture()
        rows[-1][s.SERIES[0]]=float("nan")
        with self.assertRaises(ValueError):
            s.evaluate(rows,split_round=121,replicates=100)
        with self.assertRaises(ValueError):
            s.resample({k:[0.]*100 for k in s.SERIES},block_length=101,replicates=100,seed=1)


if __name__ == "__main__":
    unittest.main()
