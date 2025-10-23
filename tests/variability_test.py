#!/usr/bin/env python3
"""
Variability test runner - runs the test suite multiple times to measure consistency.
Generates a matrix showing which tests pass/fail across multiple runs.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from test_runner import TestRunner


class VariabilityTester:
    """Runs tests multiple times and analyzes variability."""

    def __init__(self, num_runs=7, config_file="config.json"):
        self.num_runs = num_runs
        self.test_dir = Path(__file__).parent
        self.config_file = config_file
        self.results_dir = self.test_dir / "variability_results"
        self.results_dir.mkdir(exist_ok=True)

    def run_variability_tests(self):
        """Run the test suite multiple times."""
        print(f"Running test suite {self.num_runs} times...")
        print(f"This will take approximately {self.num_runs * 5} minutes.\n")

        # Load config
        config_path = self.test_dir / self.config_file
        with open(config_path, 'r') as f:
            config = json.load(f)

        # Initialize runner
        runner = TestRunner(config)

        # Collect all test files
        test_files = sorted((self.test_dir / "cases").glob("*.json"))

        all_runs = []
        start_time = time.time()

        for run_num in range(1, self.num_runs + 1):
            print(f"\n{'='*60}")
            print(f"Run {run_num}/{self.num_runs}")
            print(f"{'='*60}")

            run_start = time.time()
            results = runner.run_tests(test_files, verbose=False)
            run_duration = time.time() - run_start

            # Summarize this run
            passed = sum(1 for r in results if r["status"] == "PASS")
            total = len(results)
            print(f"\nRun {run_num} completed: {passed}/{total} passed ({passed/total*100:.0f}%) in {run_duration:.1f}s")

            all_runs.append({
                "run_number": run_num,
                "duration": run_duration,
                "passed": passed,
                "total": total,
                "results": results
            })

        total_duration = time.time() - start_time

        # Analyze and save results
        analysis = self._analyze_variability(all_runs)
        self._save_results(all_runs, analysis, total_duration)

        return analysis

    def _analyze_variability(self, all_runs):
        """Analyze consistency across runs."""
        # Build test result matrix
        test_matrix = defaultdict(list)  # test_id -> [pass/fail for each run]
        test_names = {}  # test_id -> test_name

        for run in all_runs:
            for result in run["results"]:
                test_id = result["id"]
                test_names[test_id] = result["name"]
                test_matrix[test_id].append(result["status"])

        # Calculate statistics
        test_stats = {}
        for test_id, statuses in test_matrix.items():
            passes = sum(1 for s in statuses if s == "PASS")
            fails = sum(1 for s in statuses if s == "FAIL")
            pass_rate = passes / len(statuses)

            # Categorize consistency
            if pass_rate == 1.0:
                consistency = "always_pass"
            elif pass_rate == 0.0:
                consistency = "always_fail"
            elif pass_rate >= 0.7:
                consistency = "mostly_pass"
            elif pass_rate >= 0.3:
                consistency = "inconsistent"
            else:
                consistency = "mostly_fail"

            test_stats[test_id] = {
                "name": test_names[test_id],
                "passes": passes,
                "fails": fails,
                "pass_rate": pass_rate,
                "consistency": consistency,
                "statuses": statuses
            }

        # Overall statistics
        overall_stats = {
            "total_runs": len(all_runs),
            "avg_pass_rate": sum(r["passed"] / r["total"] for r in all_runs) / len(all_runs),
            "min_pass_rate": min(r["passed"] / r["total"] for r in all_runs),
            "max_pass_rate": max(r["passed"] / r["total"] for r in all_runs),
            "avg_duration": sum(r["duration"] for r in all_runs) / len(all_runs),
        }

        return {
            "test_stats": test_stats,
            "overall_stats": overall_stats,
            "test_matrix": test_matrix
        }

    def _save_results(self, all_runs, analysis, total_duration):
        """Save variability test results."""
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        run_dir = self.results_dir / timestamp
        run_dir.mkdir(exist_ok=True)

        # Save full results
        results_data = {
            "timestamp": timestamp,
            "num_runs": self.num_runs,
            "total_duration": total_duration,
            "all_runs": all_runs,
            "analysis": {
                "test_stats": analysis["test_stats"],
                "overall_stats": analysis["overall_stats"]
            }
        }

        with open(run_dir / "full_results.json", 'w') as f:
            json.dump(results_data, f, indent=2)

        # Generate human-readable summary
        self._generate_summary_report(run_dir, analysis, total_duration)

        # Create 'latest' symlink
        latest_link = self.results_dir / "latest"
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()
        try:
            latest_link.symlink_to(run_dir.name)
        except:
            pass

        print(f"\n{'='*60}")
        print(f"Results saved to: {run_dir}")
        print(f"{'='*60}")

    def _generate_summary_report(self, run_dir, analysis, total_duration):
        """Generate a human-readable summary report."""
        test_stats = analysis["test_stats"]
        overall = analysis["overall_stats"]

        lines = []
        lines.append("="*70)
        lines.append("VARIABILITY TEST REPORT")
        lines.append("="*70)
        lines.append(f"Total runs: {self.num_runs}")
        lines.append(f"Total duration: {total_duration:.1f}s ({total_duration/60:.1f} minutes)")
        lines.append(f"Average pass rate: {overall['avg_pass_rate']*100:.1f}%")
        lines.append(f"Pass rate range: {overall['min_pass_rate']*100:.1f}% - {overall['max_pass_rate']*100:.1f}%")
        lines.append(f"Average run duration: {overall['avg_duration']:.1f}s")
        lines.append("")

        # Group tests by consistency
        by_consistency = defaultdict(list)
        for test_id, stats in sorted(test_stats.items()):
            by_consistency[stats["consistency"]].append((test_id, stats))

        lines.append("="*70)
        lines.append("TEST CONSISTENCY ANALYSIS")
        lines.append("="*70)
        lines.append("")

        # Always passing tests
        if "always_pass" in by_consistency:
            lines.append(f"✅ ALWAYS PASSING ({len(by_consistency['always_pass'])} tests):")
            for test_id, stats in by_consistency["always_pass"]:
                lines.append(f"   {test_id}: {stats['name']} [{self.num_runs}/{self.num_runs}]")
            lines.append("")

        # Mostly passing tests
        if "mostly_pass" in by_consistency:
            lines.append(f"✓  MOSTLY PASSING ({len(by_consistency['mostly_pass'])} tests):")
            for test_id, stats in by_consistency["mostly_pass"]:
                pattern = ''.join(['✓' if s == 'PASS' else '✗' for s in stats['statuses']])
                lines.append(f"   {test_id}: {stats['name']} [{stats['passes']}/{self.num_runs}] {pattern}")
            lines.append("")

        # Inconsistent tests
        if "inconsistent" in by_consistency:
            lines.append(f"⚠  INCONSISTENT ({len(by_consistency['inconsistent'])} tests):")
            for test_id, stats in by_consistency["inconsistent"]:
                pattern = ''.join(['✓' if s == 'PASS' else '✗' for s in stats['statuses']])
                lines.append(f"   {test_id}: {stats['name']} [{stats['passes']}/{self.num_runs}] {pattern}")
            lines.append("")

        # Mostly failing tests
        if "mostly_fail" in by_consistency:
            lines.append(f"✗  MOSTLY FAILING ({len(by_consistency['mostly_fail'])} tests):")
            for test_id, stats in by_consistency["mostly_fail"]:
                pattern = ''.join(['✓' if s == 'PASS' else '✗' for s in stats['statuses']])
                lines.append(f"   {test_id}: {stats['name']} [{stats['passes']}/{self.num_runs}] {pattern}")
            lines.append("")

        # Always failing tests
        if "always_fail" in by_consistency:
            lines.append(f"❌ ALWAYS FAILING ({len(by_consistency['always_fail'])} tests):")
            for test_id, stats in by_consistency["always_fail"]:
                lines.append(f"   {test_id}: {stats['name']} [0/{self.num_runs}]")
            lines.append("")

        # Matrix visualization
        lines.append("="*70)
        lines.append("TEST RESULT MATRIX")
        lines.append("="*70)
        lines.append(f"{'Test ID':<8} {'Test Name':<30} {'Results':<20}")
        lines.append("-"*70)

        for test_id, stats in sorted(test_stats.items()):
            pattern = ''.join(['✓' if s == 'PASS' else '✗' for s in stats['statuses']])
            pass_rate_str = f"{stats['pass_rate']*100:.0f}%"
            lines.append(f"{test_id:<8} {stats['name']:<30} {pattern:<15} {pass_rate_str}")

        lines.append("="*70)

        # Save to file
        summary_text = '\n'.join(lines)
        with open(run_dir / "summary.txt", 'w') as f:
            f.write(summary_text)

        # Print to console
        print("\n" + summary_text)


def main():
    parser = argparse.ArgumentParser(description="Run variability tests")
    parser.add_argument(
        "--runs",
        type=int,
        default=7,
        help="Number of times to run the test suite (default: 7)"
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        help="Config file to use (default: config.json)"
    )

    args = parser.parse_args()

    if args.runs < 2:
        print("Error: Need at least 2 runs for variability analysis")
        sys.exit(1)

    if args.runs > 20:
        print("Warning: Large number of runs will take a long time")
        response = input(f"Run test suite {args.runs} times? This could take {args.runs * 5} minutes. [y/N]: ")
        if response.lower() != 'y':
            print("Aborted")
            sys.exit(0)

    tester = VariabilityTester(num_runs=args.runs, config_file=args.config)
    tester.run_variability_tests()


if __name__ == "__main__":
    main()
