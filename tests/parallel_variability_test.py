#!/usr/bin/env python3
"""
Parallel variability test runner - runs multiple test instances concurrently.
Each run executes in a separate process to maximize throughput.
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import subprocess

class ParallelVariabilityTester:
    """Runs tests in parallel across multiple processes."""

    def __init__(self, num_runs=7, max_workers=4):
        self.num_runs = num_runs
        self.max_workers = max_workers
        self.test_dir = Path(__file__).parent
        self.results_dir = self.test_dir / "variability_results"
        self.results_dir.mkdir(exist_ok=True)

    def run_single_variability_test(self, run_num, config_file="config.json"):
        """Run a single variability test iteration in subprocess."""
        print(f"Starting run {run_num}/{self.num_runs}...")

        env = os.environ.copy()
        cmd = [
            sys.executable, "test_runner.py",
            "--no-save"  # We'll aggregate results ourselves
        ]

        if config_file != "config.json":
            cmd.extend(["--config", config_file])

        start_time = time.time()
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.test_dir),
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout per run
                env=env
            )
            duration = time.time() - start_time

            # Parse results from output
            output = result.stdout + result.stderr
            passed = output.count(" ✓ PASS")
            failed = output.count(" ✗ FAIL")
            total = passed + failed

            return {
                "run_number": run_num,
                "duration": duration,
                "passed": passed,
                "failed": failed,
                "total": total,
                "status": "success" if result.returncode == 0 else "partial",
                "output": output
            }
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return {
                "run_number": run_num,
                "duration": duration,
                "passed": 0,
                "failed": 10,
                "total": 10,
                "status": "timeout",
                "output": "Test timed out after 10 minutes"
            }
        except Exception as e:
            duration = time.time() - start_time
            return {
                "run_number": run_num,
                "duration": duration,
                "passed": 0,
                "failed": 10,
                "total": 10,
                "status": "error",
                "output": str(e)
            }

    def run_parallel_variability_tests(self, config_file="config.json"):
        """Run test suite in parallel."""
        print(f"Running {self.num_runs} test iterations in parallel (max {self.max_workers} workers)")
        print(f"Using config: {config_file}")
        print(f"Estimated time: {self.num_runs * 17 / self.max_workers / 60:.1f} minutes\n")

        all_runs = []
        start_time = time.time()

        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.run_single_variability_test, i+1, config_file): i+1
                for i in range(self.num_runs)
            }

            for future in as_completed(futures):
                run_num = futures[future]
                try:
                    result = future.result()
                    all_runs.append(result)
                    passed = result["passed"]
                    total = result["total"]
                    duration = result["duration"]
                    print(f"✓ Run {run_num} completed: {passed}/{total} passed in {duration:.1f}s")
                except Exception as e:
                    print(f"✗ Run {run_num} failed: {e}")
                    all_runs.append({
                        "run_number": run_num,
                        "duration": 0,
                        "passed": 0,
                        "failed": 10,
                        "total": 10,
                        "status": "error",
                        "output": str(e)
                    })

        total_duration = time.time() - start_time

        # Sort by run number for display
        all_runs.sort(key=lambda x: x["run_number"])

        # Analyze and save results
        analysis = self._analyze_variability(all_runs)
        self._save_results(all_runs, analysis, total_duration)

        return analysis

    def _analyze_variability(self, all_runs):
        """Analyze consistency across runs."""
        # Calculate statistics
        passed_counts = [r["passed"] for r in all_runs]
        total_counts = [r["total"] for r in all_runs]

        overall_stats = {
            "total_runs": len(all_runs),
            "avg_pass_rate": sum(r["passed"] / r["total"] for r in all_runs if r["total"] > 0) / len(all_runs),
            "min_pass_rate": min((r["passed"] / r["total"] for r in all_runs if r["total"] > 0), default=0),
            "max_pass_rate": max((r["passed"] / r["total"] for r in all_runs if r["total"] > 0), default=0),
            "avg_duration": sum(r["duration"] for r in all_runs) / len(all_runs),
            "total_duration": sum(r["duration"] for r in all_runs),
        }

        return {
            "overall_stats": overall_stats,
            "all_runs": all_runs
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
            "analysis": analysis
        }

        with open(run_dir / "full_results.json", 'w') as f:
            json.dump(results_data, f, indent=2)

        # Generate human-readable summary
        self._generate_summary_report(run_dir, analysis, total_duration)

        # Create 'latest' symlink
        latest_link = self.results_dir / "latest_parallel"
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
        overall = analysis["overall_stats"]

        lines = []
        lines.append("="*70)
        lines.append("PARALLEL VARIABILITY TEST REPORT")
        lines.append("="*70)
        lines.append(f"Total runs: {self.num_runs}")
        lines.append(f"Total duration: {total_duration:.1f}s ({total_duration/60:.1f} minutes)")
        lines.append(f"Average pass rate: {overall['avg_pass_rate']*100:.1f}%")
        lines.append(f"Pass rate range: {overall['min_pass_rate']*100:.1f}% - {overall['max_pass_rate']*100:.1f}%")
        lines.append(f"Average run duration: {overall['avg_duration']:.1f}s")
        lines.append(f"Total test time (sequential): {overall['total_duration']:.1f}s")
        lines.append(f"Speedup from parallelization: {overall['total_duration']/total_duration:.1f}x")
        lines.append("")

        # Save to file
        summary_text = '\n'.join(lines)
        with open(run_dir / "summary.txt", 'w') as f:
            f.write(summary_text)

        # Print to console
        print("\n" + summary_text)


def main():
    parser = argparse.ArgumentParser(description="Run variability tests in parallel")
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
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Number of parallel workers (default: 4)"
    )

    args = parser.parse_args()

    if args.runs < 2:
        print("Error: Need at least 2 runs for variability analysis")
        sys.exit(1)

    if args.workers < 1:
        print("Error: Need at least 1 worker")
        sys.exit(1)

    tester = ParallelVariabilityTester(num_runs=args.runs, max_workers=args.workers)
    tester.run_parallel_variability_tests(config_file=args.config)


if __name__ == "__main__":
    main()
