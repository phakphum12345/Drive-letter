import unittest

from tools.research_os_capacity_metrics import nearest_rank_percentile, summarize_samples


class CapacityMetricsTests(unittest.TestCase):
    def test_nearest_rank_percentiles(self):
        values = [50, 10, 40, 20, 30]
        self.assertEqual(10.0, nearest_rank_percentile(values, 1))
        self.assertEqual(30.0, nearest_rank_percentile(values, 50))
        self.assertEqual(50.0, nearest_rank_percentile(values, 95))
        self.assertEqual(50.0, nearest_rank_percentile(values, 99))

    def test_empty_percentile_returns_none(self):
        self.assertIsNone(nearest_rank_percentile([], 95))

    def test_invalid_percentile_is_rejected(self):
        with self.assertRaises(ValueError):
            nearest_rank_percentile([1, 2], 0)

    def test_summary_counts_failures_and_throughput(self):
        samples = [
            {"latency_ms": 10, "status": 200, "error": None},
            {"latency_ms": 30, "status": 503, "error": "http_status"},
            {"latency_ms": 20, "status": None, "error": "TimeoutError"},
        ]
        report = summarize_samples(samples, 2.0)
        self.assertEqual(3, report["requests_completed"])
        self.assertEqual(1, report["requests_succeeded"])
        self.assertEqual(2, report["requests_failed"])
        self.assertEqual(0.666667, report["error_rate"])
        self.assertEqual(1.5, report["throughput_requests_per_second"])
        self.assertEqual({"200": 1, "503": 1}, report["http_status_counts"])
        self.assertEqual(30.0, report["latency_ms"]["p95"])

    def test_zero_elapsed_time_has_no_throughput(self):
        report = summarize_samples(
            [{"latency_ms": 5, "status": 200, "error": None}], 0
        )
        self.assertIsNone(report["throughput_requests_per_second"])

    def test_empty_samples_keep_unknown_values_null(self):
        report = summarize_samples([], 0)
        self.assertIsNone(report["error_rate"])
        self.assertIsNone(report["latency_ms"]["p99"])
        self.assertIsNone(report["throughput_requests_per_second"])


if __name__ == "__main__":
    unittest.main()
