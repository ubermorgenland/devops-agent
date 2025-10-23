"""
Test validation logic for ollama_devops agent tests.
Validates test results against assertions without using LLMs.
"""
import os
import re
from typing import Dict, List, Any, Optional


class TestValidator:
    """Validates test execution results against assertions."""

    def __init__(self, test_dir: str):
        self.test_dir = test_dir

    def validate_assertions(self, assertions: List[Dict], execution_result: Dict) -> Dict:
        """
        Validate all assertions for a test case.

        Args:
            assertions: List of assertion definitions
            execution_result: Result from test execution containing:
                - tool_calls: List of tool calls made
                - final_answer: Final answer from agent
                - steps: Number of steps taken
                - errors: List of errors encountered
                - temp_dir: Path to temp directory with files

        Returns:
            Dict with validation results:
                - passed: int
                - failed: int
                - failures: List of failure details
        """
        passed = 0
        failed = 0
        failures = []

        for assertion in assertions:
            assertion_type = assertion.get("type")

            try:
                result = self._validate_single_assertion(assertion, execution_result)
                if result["passed"]:
                    passed += 1
                else:
                    failed += 1
                    failures.append({
                        "assertion": assertion_type,
                        "reason": result["reason"],
                        "expected": result.get("expected"),
                        "actual": result.get("actual")
                    })
            except Exception as e:
                failed += 1
                failures.append({
                    "assertion": assertion_type,
                    "reason": f"Assertion validation error: {str(e)}",
                    "exception": str(e)
                })

        return {
            "passed": passed,
            "failed": failed,
            "failures": failures
        }

    def _validate_single_assertion(self, assertion: Dict, execution_result: Dict) -> Dict:
        """Validate a single assertion."""
        assertion_type = assertion.get("type")

        validators = {
            "tool_called": self._validate_tool_called,
            "tool_not_called": self._validate_tool_not_called,
            "tool_call_count": self._validate_tool_call_count,
            "file_exists": self._validate_file_exists,
            "file_not_exists": self._validate_file_not_exists,
            "file_content_contains": self._validate_file_content_contains,
            "file_content_matches": self._validate_file_content_matches,
            "completed_successfully": self._validate_completed_successfully,
            "final_answer_contains": self._validate_final_answer_contains,
            "no_tool_errors": self._validate_no_tool_errors,
            "steps_within": self._validate_steps_within,
        }

        validator = validators.get(assertion_type)
        if not validator:
            return {
                "passed": False,
                "reason": f"Unknown assertion type: {assertion_type}"
            }

        return validator(assertion, execution_result)

    # Tool assertions

    def _validate_tool_called(self, assertion: Dict, execution_result: Dict) -> Dict:
        """Check if a specific tool was called with optional args."""
        tool_name = assertion.get("tool")
        expected_args = assertion.get("args", {})

        tool_calls = execution_result.get("tool_calls", [])

        for call in tool_calls:
            if call.get("name") == tool_name:
                # If args specified, check if they match
                if expected_args:
                    call_args = call.get("arguments", {})
                    if all(call_args.get(k) == v for k, v in expected_args.items()):
                        return {"passed": True}
                else:
                    # No args specified, just check tool was called
                    return {"passed": True}

        return {
            "passed": False,
            "reason": f"Tool '{tool_name}' was not called with expected arguments",
            "expected": {"tool": tool_name, "args": expected_args},
            "actual": [{"name": c.get("name"), "args": c.get("arguments")} for c in tool_calls]
        }

    def _validate_tool_not_called(self, assertion: Dict, execution_result: Dict) -> Dict:
        """Check that a specific tool was NOT called."""
        tool_name = assertion.get("tool")
        tool_calls = execution_result.get("tool_calls", [])

        for call in tool_calls:
            if call.get("name") == tool_name:
                return {
                    "passed": False,
                    "reason": f"Tool '{tool_name}' should not have been called",
                    "actual": call
                }

        return {"passed": True}

    def _validate_tool_call_count(self, assertion: Dict, execution_result: Dict) -> Dict:
        """Check tool was called exactly N times."""
        tool_name = assertion.get("tool")
        expected_count = assertion.get("count")

        tool_calls = execution_result.get("tool_calls", [])
        actual_count = sum(1 for call in tool_calls if call.get("name") == tool_name)

        if actual_count == expected_count:
            return {"passed": True}

        return {
            "passed": False,
            "reason": f"Tool '{tool_name}' called {actual_count} times, expected {expected_count}",
            "expected": expected_count,
            "actual": actual_count
        }

    # File assertions

    def _validate_file_exists(self, assertion: Dict, execution_result: Dict) -> Dict:
        """Check that a file exists in the temp directory."""
        file_path = assertion.get("path")
        temp_dir = execution_result.get("temp_dir")

        full_path = os.path.join(temp_dir, file_path)

        if os.path.exists(full_path):
            return {"passed": True}

        return {
            "passed": False,
            "reason": f"File '{file_path}' does not exist",
            "expected": f"File exists at {full_path}",
            "actual": "File not found"
        }

    def _validate_file_not_exists(self, assertion: Dict, execution_result: Dict) -> Dict:
        """Check that a file does NOT exist."""
        file_path = assertion.get("path")
        temp_dir = execution_result.get("temp_dir")

        full_path = os.path.join(temp_dir, file_path)

        if not os.path.exists(full_path):
            return {"passed": True}

        return {
            "passed": False,
            "reason": f"File '{file_path}' should not exist",
            "actual": f"File found at {full_path}"
        }

    def _validate_file_content_contains(self, assertion: Dict, execution_result: Dict) -> Dict:
        """Check file content contains expected strings."""
        file_path = assertion.get("path")
        expected_values = assertion.get("values", [])
        case_sensitive = assertion.get("case_sensitive", True)
        match_any = assertion.get("match_any", False)

        temp_dir = execution_result.get("temp_dir")
        full_path = os.path.join(temp_dir, file_path)

        if not os.path.exists(full_path):
            return {
                "passed": False,
                "reason": f"File '{file_path}' does not exist",
                "expected": expected_values
            }

        with open(full_path, 'r') as f:
            content = f.read()

        if not case_sensitive:
            content = content.lower()
            expected_values = [v.lower() for v in expected_values]

        if match_any:
            # At least one value must be present
            found = any(v in content for v in expected_values)
            if found:
                return {"passed": True}
            return {
                "passed": False,
                "reason": f"None of the expected values found in {file_path}",
                "expected": expected_values,
                "actual": content[:200]  # First 200 chars
            }
        else:
            # All values must be present
            missing = [v for v in expected_values if v not in content]
            if not missing:
                return {"passed": True}
            return {
                "passed": False,
                "reason": f"Missing values in {file_path}: {missing}",
                "expected": expected_values,
                "actual": content[:200]
            }

    def _validate_file_content_matches(self, assertion: Dict, execution_result: Dict) -> Dict:
        """Check file content matches regex pattern."""
        file_path = assertion.get("path")
        pattern = assertion.get("pattern")

        temp_dir = execution_result.get("temp_dir")
        full_path = os.path.join(temp_dir, file_path)

        if not os.path.exists(full_path):
            return {
                "passed": False,
                "reason": f"File '{file_path}' does not exist",
                "expected": f"Pattern: {pattern}"
            }

        with open(full_path, 'r') as f:
            content = f.read()

        if re.search(pattern, content):
            return {"passed": True}

        return {
            "passed": False,
            "reason": f"Content does not match pattern in {file_path}",
            "expected": f"Pattern: {pattern}",
            "actual": content[:200]
        }

    # Output assertions

    def _validate_completed_successfully(self, assertion: Dict, execution_result: Dict) -> Dict:
        """Check that test completed without errors and within step limit."""
        errors = execution_result.get("errors", [])
        max_steps = execution_result.get("max_steps")
        steps = execution_result.get("steps", 0)

        if errors:
            return {
                "passed": False,
                "reason": "Test completed with errors",
                "actual": errors
            }

        if max_steps and steps > max_steps:
            return {
                "passed": False,
                "reason": f"Exceeded max steps: {steps} > {max_steps}",
                "expected": f"<= {max_steps} steps",
                "actual": f"{steps} steps"
            }

        return {"passed": True}

    def _validate_final_answer_contains(self, assertion: Dict, execution_result: Dict) -> Dict:
        """Check final answer contains expected values."""
        expected_values = assertion.get("values", [])
        case_sensitive = assertion.get("case_sensitive", True)
        match_any = assertion.get("match_any", False)

        final_answer = execution_result.get("final_answer", "")

        if not case_sensitive:
            final_answer = final_answer.lower()
            expected_values = [v.lower() for v in expected_values]

        if match_any:
            found = any(v in final_answer for v in expected_values)
            if found:
                return {"passed": True}
            return {
                "passed": False,
                "reason": "None of the expected values found in final answer",
                "expected": expected_values,
                "actual": final_answer
            }
        else:
            missing = [v for v in expected_values if v not in final_answer]
            if not missing:
                return {"passed": True}
            return {
                "passed": False,
                "reason": f"Missing values in final answer: {missing}",
                "expected": expected_values,
                "actual": final_answer
            }

    def _validate_no_tool_errors(self, assertion: Dict, execution_result: Dict) -> Dict:
        """Check that no tool execution errors occurred."""
        errors = execution_result.get("errors", [])
        tool_errors = [e for e in errors if "tool" in e.lower() or "error executing" in e.lower()]

        if not tool_errors:
            return {"passed": True}

        return {
            "passed": False,
            "reason": "Tool execution errors occurred",
            "actual": tool_errors
        }

    def _validate_steps_within(self, assertion: Dict, execution_result: Dict) -> Dict:
        """Check that execution completed within step limit."""
        max_steps = assertion.get("max")
        actual_steps = execution_result.get("steps", 0)

        if actual_steps <= max_steps:
            return {"passed": True}

        return {
            "passed": False,
            "reason": f"Exceeded step limit: {actual_steps} > {max_steps}",
            "expected": f"<= {max_steps} steps",
            "actual": f"{actual_steps} steps"
        }
