#!/usr/bin/env python3
"""
Test runner for ollama_devops agent tests.
Executes test cases and validates results without using LLMs.
"""
import argparse
import json
import os
import sys
import tempfile
import shutil
import time
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add parent directory to path to import agent modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import DevOpsAgent, read_file, write_file, bash, get_env
from ollama_backend import OllamaChat
try:
    from openrouter_backend import OpenRouterChat
except ImportError:
    OpenRouterChat = None
from test_validator import TestValidator


class TestRunner:
    """Runs test cases and validates results."""

    def __init__(self, config: Dict):
        self.config = config
        self.test_dir = Path(__file__).parent
        self.validator = TestValidator(str(self.test_dir))
        self.results_dir = self.test_dir / "results"

    def load_test_case(self, test_file: Path) -> Dict:
        """Load a test case from JSON file."""
        with open(test_file, 'r') as f:
            return json.load(f)

    def setup_test_environment(self, test_case: Dict) -> tuple[str, Dict]:
        """
        Setup test environment (temp dir, env vars, files).

        Returns:
            Tuple of (temp_dir_path, env_vars_dict)
        """
        # Create temp directory
        temp_dir = tempfile.mkdtemp(prefix=self.config.get("temp_dir_prefix", "ollama_test_"))

        # Setup environment variables
        env_vars = test_case.get("setup", {}).get("env_vars", {})

        # Create fixture files in temp dir
        files = test_case.get("setup", {}).get("files", {})
        for file_path, content in files.items():
            full_path = os.path.join(temp_dir, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w') as f:
                f.write(content)

        return temp_dir, env_vars

    def execute_test(self, test_case: Dict, temp_dir: str, env_vars: Dict) -> Dict:
        """
        Execute a single test case.

        Returns:
            Dict with execution results
        """
        start_time = time.time()

        # Change to temp directory
        original_dir = os.getcwd()
        os.chdir(temp_dir)

        # Set environment variables
        original_env = {}
        for key, value in env_vars.items():
            original_env[key] = os.environ.get(key)
            os.environ[key] = value

        # Track tool calls
        tool_calls_tracker = []

        # Store original tool __call__ methods
        original_calls = {}
        for tool in [read_file, write_file, bash, get_env]:
            tool_name = tool.name
            original_calls[tool_name] = tool.forward

            # Create tracking wrapper
            def make_wrapper(tname, orig_forward):
                def tracked_forward(*args, **kwargs):
                    tool_calls_tracker.append({
                        "name": tname,
                        "arguments": kwargs
                    })
                    return orig_forward(*args, **kwargs)
                return tracked_forward

            # Monkey-patch the tool
            tool.forward = make_wrapper(tool_name, tool.forward)

        try:
            # Initialize agent with appropriate backend
            backend_type = self.config.get("backend", "ollama")
            model_name = self.config.get("default_model", "qwen3:1.7b")

            if backend_type == "openrouter" and OpenRouterChat:
                model = OpenRouterChat(model=model_name)
            else:
                model = OllamaChat(model=model_name)

            agent = DevOpsAgent(
                tools=[read_file, write_file, bash, get_env],
                model=model,
                instructions="You are a DevOps automation assistant; use the tools provided and call no other code.",
                max_steps=test_case.get("max_steps", self.config.get("default_max_steps", 4))
            )
            model.tools = agent.tools

            # Execute instruction
            instruction = test_case.get("instruction")
            result = agent.run(instruction)

            # Extract step count from agent
            steps = self._extract_step_count_from_agent(agent)

            # Collect any errors
            errors = self._extract_errors_from_agent(agent)

            duration = time.time() - start_time

            return {
                "tool_calls": tool_calls_tracker,
                "final_answer": str(result),
                "steps": steps,
                "errors": errors,
                "temp_dir": temp_dir,
                "max_steps": test_case.get("max_steps", self.config.get("default_max_steps", 4)),
                "duration": duration,
                "status": "completed"
            }

        except Exception as e:
            duration = time.time() - start_time
            return {
                "tool_calls": tool_calls_tracker,
                "final_answer": "",
                "steps": 0,
                "errors": [str(e)],
                "temp_dir": temp_dir,
                "max_steps": test_case.get("max_steps", self.config.get("default_max_steps", 4)),
                "duration": duration,
                "status": "error",
                "exception": str(e)
            }

        finally:
            # Restore original tool methods
            for tool in [read_file, write_file, bash, get_env]:
                if tool.name in original_calls:
                    tool.forward = original_calls[tool.name]

            # Restore environment
            os.chdir(original_dir)
            for key, value in original_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def _extract_step_count_from_agent(self, agent: DevOpsAgent) -> int:
        """Extract number of steps from agent execution."""
        # Try to get step count from agent's internal state
        if hasattr(agent, '_step_count'):
            return agent._step_count
        if hasattr(agent, 'logs') and agent.logs:
            return len(agent.logs)
        # Fallback: count from agent's internal state
        return 0

    def _extract_errors_from_agent(self, agent: DevOpsAgent) -> List[str]:
        """Extract errors from agent execution."""
        errors = []
        # Check if agent has error tracking
        if hasattr(agent, 'logs') and agent.logs:
            for log_entry in agent.logs:
                if isinstance(log_entry, dict):
                    content = log_entry.get('content', '')
                    if 'error' in str(content).lower() or 'failed' in str(content).lower():
                        errors.append(str(content))
        return errors

    def cleanup_test_environment(self, temp_dir: str):
        """Clean up temp directory after test."""
        if self.config.get("cleanup_temp_dirs", True):
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                print(f"Warning: Failed to clean up temp dir {temp_dir}: {e}")

    def save_results(self, test_results: List[Dict], timestamp: str):
        """Save test results to disk."""
        if not self.config.get("save_results", True):
            return None

        # Create results directory for this run
        run_dir = self.results_dir / timestamp
        run_dir.mkdir(parents=True, exist_ok=True)

        # Calculate summary statistics
        total = len(test_results)
        passed = sum(1 for r in test_results if r["status"] == "PASS")
        failed = total - passed
        pass_rate = passed / total if total > 0 else 0
        total_duration = sum(r["duration"] for r in test_results)

        summary = {
            "timestamp": timestamp,
            "model": self.config.get("default_model"),
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": pass_rate,
            "total_duration": total_duration,
            "results": test_results
        }

        # Save summary JSON
        with open(run_dir / "summary.json", 'w') as f:
            json.dump(summary, f, indent=2)

        # Save individual test results if configured
        if self.config.get("save_full_logs", True):
            for result in test_results:
                result_file = run_dir / f"{result['id']}_{result['name']}_result.json"
                with open(result_file, 'w') as f:
                    json.dump(result, f, indent=2)

        # Create 'latest' symlink
        latest_link = self.results_dir / "latest"
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()
        try:
            latest_link.symlink_to(run_dir.name)
        except:
            pass  # Symlinks may not work on all systems

        return str(run_dir)

    def run_tests(self, test_files: List[Path], verbose: bool = False) -> List[Dict]:
        """Run all test cases and return results."""
        results = []
        total = len(test_files)

        print(f"Running tests with model: {self.config.get('default_model')}")
        print(f"Total tests: {total}\n")

        for idx, test_file in enumerate(test_files, 1):
            # Load test case
            test_case = self.load_test_case(test_file)
            test_id = test_case.get("id", "unknown")
            test_name = test_case.get("name", test_file.stem)

            if verbose:
                print(f"\n[{idx}/{total}] Running {test_name} (ID: {test_id})")
                print(f"  Instruction: {test_case.get('instruction')}")

            # Setup environment
            temp_dir, env_vars = self.setup_test_environment(test_case)

            if verbose:
                print(f"  Temp dir: {temp_dir}")

            # Execute test
            execution_result = self.execute_test(test_case, temp_dir, env_vars)

            # Validate assertions
            assertions = test_case.get("assertions", [])
            validation_result = self.validator.validate_assertions(assertions, execution_result)

            # Determine test status
            test_status = "PASS" if validation_result["failed"] == 0 else "FAIL"

            # Compile result
            result = {
                "id": test_id,
                "name": test_name,
                "category": test_case.get("category", "uncategorized"),
                "status": test_status,
                "duration": execution_result["duration"],
                "steps": execution_result["steps"],
                "assertions_passed": validation_result["passed"],
                "assertions_failed": validation_result["failed"],
                "failures": validation_result["failures"],
                "final_answer": execution_result["final_answer"],
                "tool_calls": execution_result["tool_calls"],
                "errors": execution_result["errors"]
            }

            results.append(result)

            # Print result
            status_symbol = "✓" if test_status == "PASS" else "✗"
            duration_str = f"{execution_result['duration']:.1f}s"
            steps_str = f"{execution_result['steps']} steps"
            dots = "." * max(1, 50 - len(test_name))

            print(f"[{idx}/{total}] {test_name} {dots} {status_symbol} {test_status} ({duration_str}, {steps_str})")

            if test_status == "FAIL" and not verbose:
                for failure in validation_result["failures"]:
                    print(f"  ✗ {failure['assertion']}: {failure['reason']}")

            if verbose and validation_result["failures"]:
                print(f"  Failures:")
                for failure in validation_result["failures"]:
                    print(f"    - {failure['assertion']}: {failure['reason']}")
                    if "expected" in failure:
                        print(f"      Expected: {failure['expected']}")
                    if "actual" in failure:
                        print(f"      Actual: {failure['actual']}")

            # Cleanup
            if not verbose:  # Keep temp dir in verbose mode for debugging
                self.cleanup_test_environment(temp_dir)

        return results

    def print_summary(self, results: List[Dict]):
        """Print test run summary."""
        total = len(results)
        passed = sum(1 for r in results if r["status"] == "PASS")
        failed = total - passed
        pass_rate = (passed / total * 100) if total > 0 else 0
        total_duration = sum(r["duration"] for r in results)

        print(f"\n{'='*60}")
        print(f"Summary: {passed}/{total} passed ({pass_rate:.0f}%)")
        print(f"Total time: {total_duration:.1f}s")
        print(f"{'='*60}")


def main():
    """Main entry point for test runner."""
    parser = argparse.ArgumentParser(description="Run ollama_devops agent tests")
    parser.add_argument("--test", nargs="+", help="Specific test IDs to run")
    parser.add_argument("--category", help="Run tests by category")
    parser.add_argument("--no-save", action="store_true", help="Don't save results")
    parser.add_argument("--model", help="Model to use (overrides config)")
    parser.add_argument("--config", help="Config file to use (default: config.json)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first failure")

    args = parser.parse_args()

    # Load configuration
    test_dir = Path(__file__).parent
    config_file = test_dir / (args.config or "config.json")

    with open(config_file, 'r') as f:
        config = json.load(f)

    # Apply command-line overrides
    if args.no_save:
        config["save_results"] = False
    if args.model:
        config["default_model"] = args.model
    if args.verbose:
        config["verbose"] = True

    # Find test files
    cases_dir = test_dir / "cases"
    test_files = sorted(cases_dir.glob("*.json"))

    # Filter by test ID if specified
    if args.test:
        test_ids = set(args.test)
        test_files = [f for f in test_files if any(tid in f.stem for tid in test_ids)]

    # Filter by category if specified
    if args.category:
        filtered = []
        for test_file in test_files:
            with open(test_file, 'r') as f:
                test_case = json.load(f)
                if test_case.get("category") == args.category:
                    filtered.append(test_file)
        test_files = filtered

    if not test_files:
        print("No test files found!")
        sys.exit(1)

    # Run tests
    runner = TestRunner(config)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    results = runner.run_tests(test_files, verbose=args.verbose)

    # Print summary
    runner.print_summary(results)

    # Save results
    if config.get("save_results", True):
        results_path = runner.save_results(results, timestamp)
        if results_path:
            print(f"Results saved to: {results_path}")

    # Exit with error code if any tests failed
    failed_count = sum(1 for r in results if r["status"] == "FAIL")
    sys.exit(1 if failed_count > 0 else 0)


if __name__ == "__main__":
    main()
