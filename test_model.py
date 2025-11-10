#!/usr/bin/env python3
"""Test script to verify the model is working correctly"""

import subprocess
import sys
import re
from collections import defaultdict

# Test queries - covering different types of tasks
TEST_QUERIES = [
    "Get all pods in default namespace",
    "List all Docker containers",
    "Create a simple Dockerfile for Python",
    "Check disk usage",
    "Get PATH environment variable",
]

def run_query(query):
    """Run a single query and collect results"""
    print(f"\n{'='*80}")
    print(f"Testing: {query}")
    print('='*80)

    result = {
        'query': query,
        'success': False,
        'errors': [],
        'steps': 0,
        'json_errors': 0,
        'tool_calls': 0,
        'output': ''
    }

    try:
        # Run the agent
        proc = subprocess.run(
            ['python3', 'agent.py', query],
            capture_output=True,
            text=True,
            timeout=60
        )

        output = proc.stdout + proc.stderr
        result['output'] = output

        # Count steps
        steps = re.findall(r'Step (\d+)', output)
        result['steps'] = len(steps)

        # Count JSON parsing errors
        json_errors = re.findall(r'Failed to parse tool call JSON', output)
        result['json_errors'] = len(json_errors)

        # Count tool calls (successful ones in boxes)
        tool_calls = re.findall(r"Calling tool: '(\w+)'", output)
        result['tool_calls'] = len(tool_calls)

        # Check for final result
        if '✅ Result:' in output:
            result['success'] = True

        # Collect specific errors
        if 'WARNING' in output or 'ERROR' in output:
            warnings = re.findall(r'(⚠️.*?)\n', output)
            errors = re.findall(r'(❌.*?)\n', output)
            result['errors'] = warnings + errors

        # Print summary
        print(f"✓ Steps: {result['steps']}")
        print(f"✓ Tool calls: {result['tool_calls']}")
        if result['json_errors'] > 0:
            print(f"❌ JSON errors: {result['json_errors']}")
        if result['errors']:
            print(f"⚠️  Warnings/Errors: {len(result['errors'])}")
            for err in result['errors'][:3]:  # Show first 3
                print(f"   {err}")

        if result['success']:
            print("✅ PASSED")
        else:
            print("❌ FAILED")

    except subprocess.TimeoutExpired:
        print("❌ TIMEOUT (60s)")
        result['errors'].append("Timeout after 60 seconds")
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        result['errors'].append(str(e))

    return result

def main():
    print("\n" + "="*80)
    print("MODEL TEST SUITE")
    print("="*80)

    results = []
    for query in TEST_QUERIES:
        result = run_query(query)
        results.append(result)

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)

    passed = sum(1 for r in results if r['success'] and r['json_errors'] == 0)
    failed = len(results) - passed
    total_json_errors = sum(r['json_errors'] for r in results)
    total_steps = sum(r['steps'] for r in results)
    total_tools = sum(r['tool_calls'] for r in results)

    print(f"\nTests run: {len(results)}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"\nTotal steps: {total_steps}")
    print(f"Total tool calls: {total_tools}")
    print(f"JSON parsing errors: {total_json_errors}")

    if total_json_errors > 0:
        print(f"\n⚠️  WARNING: {total_json_errors} JSON parsing errors detected!")
        print("This indicates the model is generating malformed tool calls.")

    print("\nDetailed Results:")
    print("-" * 80)
    for r in results:
        status = "✅ PASS" if (r['success'] and r['json_errors'] == 0) else "❌ FAIL"
        print(f"{status} | {r['query'][:50]:50s} | Steps: {r['steps']} | Tools: {r['tool_calls']} | JSON Errors: {r['json_errors']}")

    # Exit code
    sys.exit(0 if failed == 0 and total_json_errors == 0 else 1)

if __name__ == "__main__":
    main()
