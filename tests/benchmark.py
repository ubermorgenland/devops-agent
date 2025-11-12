#!/usr/bin/env python3
"""
Benchmark script to measure Ollama backend performance consistency.
Runs multiple iterations and calculates average, std, min, max response times.
"""
import time
import statistics
import os
import sys

# Suppress verbose output
os.environ['DEBUG_OLLAMA'] = '0'
os.environ['SMOLAGENTS_LOG_LEVEL'] = 'WARNING'
os.environ['VERBOSE'] = '0'

from agent import agent

def run_single_test(query):
    """Run a single agent query and return the execution time."""
    start = time.time()
    try:
        result = agent.run(query)
        end = time.time()
        return end - start, True, result
    except Exception as e:
        end = time.time()
        return end - start, False, str(e)

def benchmark(query, iterations=10):
    """Run benchmark with multiple iterations."""
    print(f"🔬 Benchmarking Ollama backend")
    print(f"📋 Query: {query}")
    print(f"🔁 Iterations: {iterations}\n")

    times = []
    successful = 0

    for i in range(1, iterations + 1):
        print(f"Running iteration {i}/{iterations}...", end=' ', flush=True)
        duration, success, result = run_single_test(query)
        times.append(duration)

        if success:
            successful += 1
            print(f"✅ {duration:.2f}s")
        else:
            print(f"❌ {duration:.2f}s (failed: {result[:50]})")

    # Calculate statistics
    print(f"\n{'='*60}")
    print(f"📊 RESULTS")
    print(f"{'='*60}")
    print(f"Successful runs: {successful}/{iterations}")
    print(f"Average time:    {statistics.mean(times):.2f}s")
    print(f"Std deviation:   {statistics.stdev(times):.2f}s" if len(times) > 1 else "Std deviation:   N/A")
    print(f"Min time:        {min(times):.2f}s")
    print(f"Max time:        {max(times):.2f}s")
    print(f"Median time:     {statistics.median(times):.2f}s")
    print(f"\n📈 All times: {[f'{t:.2f}s' for t in times]}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    # Default test query - simple but requires kubectl access
    query = "Get all pods in default namespace"
    iterations = 10

    # Allow command line override
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])

    benchmark(query, iterations)
