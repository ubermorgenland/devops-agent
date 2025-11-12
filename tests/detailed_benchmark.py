#!/usr/bin/env python3
"""
Comprehensive benchmark with JSON parsing tracking and Ollama timing metrics.
Tests both default and keep_alive configurations.
"""
import time
import statistics
import os
import sys
import json
import requests

os.environ['DEBUG_OLLAMA'] = '0'
os.environ['SMOLAGENTS_LOG_LEVEL'] = 'WARNING'
os.environ['VERBOSE'] = '0'

from agent import agent
from ollama_backend import OllamaChat

class DetailedBenchmark:
    def __init__(self):
        self.results = []

    def run_single_test(self, query):
        """Run single test and capture all metrics."""
        start_time = time.time()

        result = {
            'success': False,
            'total_time': 0,
            'json_parse_errors': 0,
            'steps_taken': 0,
            'ollama_metrics': []
        }

        # Monkey-patch to capture Ollama responses
        original_post = requests.post
        def capturing_post(url, *args, **kwargs):
            resp = original_post(url, *args, **kwargs)
            if 'ollama' in url and resp.ok:
                try:
                    data = resp.json()
                    if 'total_duration' in data:
                        result['ollama_metrics'].append({
                            'total_duration': data.get('total_duration', 0) / 1e9,
                            'load_duration': data.get('load_duration', 0) / 1e9,
                            'prompt_eval_duration': data.get('prompt_eval_duration', 0) / 1e9,
                            'prompt_eval_count': data.get('prompt_eval_count', 0),
                            'eval_duration': data.get('eval_duration', 0) / 1e9,
                            'eval_count': data.get('eval_count', 0),
                        })
                except:
                    pass
            return resp

        requests.post = capturing_post

        # Count JSON parse failures from agent logs
        import io
        from contextlib import redirect_stdout, redirect_stderr

        captured_output = io.StringIO()
        captured_errors = io.StringIO()

        try:
            with redirect_stdout(captured_output), redirect_stderr(captured_errors):
                agent_result = agent.run(query)

            result['success'] = True
            result['total_time'] = time.time() - start_time

            # Count JSON parse errors in output
            output = captured_output.getvalue() + captured_errors.getvalue()
            result['json_parse_errors'] = output.count('WARNING: Failed to parse tool call JSON')
            result['steps_taken'] = output.count('Step ')

        except Exception as e:
            result['success'] = False
            result['total_time'] = time.time() - start_time
            result['error'] = str(e)
        finally:
            requests.post = original_post

        return result

    def run_benchmark(self, query, iterations=20, test_name="Default"):
        """Run full benchmark."""
        print(f"\n{'='*70}")
        print(f"🔬 BENCHMARK: {test_name}")
        print(f"{'='*70}")
        print(f"Query: {query}")
        print(f"Iterations: {iterations}\n")

        for i in range(1, iterations + 1):
            print(f"Run {i:2d}/{iterations}...", end=' ', flush=True)
            result = self.run_single_test(query)
            self.results.append(result)

            if result['success']:
                print(f"✅ {result['total_time']:5.2f}s | Steps: {result['steps_taken']:2d} | JSON errors: {result['json_parse_errors']}")
            else:
                print(f"❌ {result['total_time']:5.2f}s | FAILED")

        self.print_summary()

    def print_summary(self):
        """Print detailed summary statistics."""
        total = len(self.results)
        successful = [r for r in self.results if r['success']]
        failed = [r for r in self.results if not r['success']]

        times = [r['total_time'] for r in self.results]
        json_errors = [r['json_parse_errors'] for r in self.results]
        steps = [r['steps_taken'] for r in self.results]

        print(f"\n{'='*70}")
        print(f"📊 SUMMARY")
        print(f"{'='*70}")
        print(f"Success rate:     {len(successful)}/{total} ({len(successful)/total*100:.1f}%)")
        print(f"Failed runs:      {len(failed)}")
        print(f"\n--- TIMING ---")
        print(f"Average time:     {statistics.mean(times):.2f}s")
        print(f"Std deviation:    {statistics.stdev(times):.2f}s")
        print(f"Min time:         {min(times):.2f}s")
        print(f"Max time:         {max(times):.2f}s")
        print(f"Median time:      {statistics.median(times):.2f}s")
        print(f"CV (variance):    {(statistics.stdev(times) / statistics.mean(times) * 100):.1f}%")

        print(f"\n--- JSON PARSING ---")
        runs_with_errors = len([r for r in self.results if r['json_parse_errors'] > 0])
        print(f"Runs with JSON errors:  {runs_with_errors}/{total} ({runs_with_errors/total*100:.1f}%)")
        print(f"Total JSON errors:      {sum(json_errors)}")
        print(f"Avg errors per run:     {statistics.mean(json_errors):.1f}")

        print(f"\n--- AGENT STEPS ---")
        print(f"Average steps:    {statistics.mean(steps):.1f}")
        print(f"Min steps:        {min(steps)}")
        print(f"Max steps:        {max(steps)}")

        # Ollama metrics analysis
        all_metrics = []
        for r in self.results:
            all_metrics.extend(r['ollama_metrics'])

        if all_metrics:
            print(f"\n--- OLLAMA DETAILED METRICS (per API call) ---")
            avg_total = statistics.mean([m['total_duration'] for m in all_metrics])
            avg_load = statistics.mean([m['load_duration'] for m in all_metrics])
            avg_prompt = statistics.mean([m['prompt_eval_duration'] for m in all_metrics])
            avg_eval = statistics.mean([m['eval_duration'] for m in all_metrics])
            avg_prompt_tokens = statistics.mean([m['prompt_eval_count'] for m in all_metrics])
            avg_eval_tokens = statistics.mean([m['eval_count'] for m in all_metrics])

            print(f"Avg total duration:     {avg_total:.2f}s")
            print(f"Avg load time:          {avg_load:.2f}s ({avg_load/avg_total*100:.1f}%)")
            print(f"Avg prompt eval:        {avg_prompt:.2f}s ({avg_prompt/avg_total*100:.1f}%) - {avg_prompt_tokens:.0f} tokens")
            print(f"Avg token generation:   {avg_eval:.2f}s ({avg_eval/avg_total*100:.1f}%) - {avg_eval_tokens:.0f} tokens")
            print(f"Prompt tokens/sec:      {avg_prompt_tokens/avg_prompt:.0f} t/s")
            print(f"Generation tokens/sec:  {avg_eval_tokens/avg_eval:.0f} t/s")

            # First vs subsequent calls
            if len(all_metrics) > 1:
                first_load = all_metrics[0]['load_duration']
                subsequent_loads = [m['load_duration'] for m in all_metrics[1:]]
                print(f"\n--- COLD START ANALYSIS ---")
                print(f"First call load time:      {first_load:.2f}s")
                print(f"Subsequent avg load time:  {statistics.mean(subsequent_loads):.2f}s")
                print(f"Cold start penalty:        {first_load - statistics.mean(subsequent_loads):.2f}s")

        print(f"\n📈 All times: {[f'{t:.2f}s' for t in times]}")
        print(f"{'='*70}\n")


if __name__ == "__main__":
    query = "Get all pods in default namespace"

    # Test 1: Default configuration
    benchmark1 = DetailedBenchmark()
    benchmark1.run_benchmark(query, iterations=20, test_name="Default (5min keep_alive)")

    print("\n" + "="*70)
    print("🔄 Now testing with extended keep_alive...")
    print("="*70)

    # Preload model with extended keep_alive
    print("Preloading model with keep_alive=30m...")
    try:
        resp = requests.post('http://localhost:11434/api/generate', json={
            'model': 'qwen-devops-v2',
            'prompt': '',
            'keep_alive': '30m'
        })
        print("✅ Model preloaded\n")
    except Exception as e:
        print(f"⚠️  Could not preload: {e}\n")

    # Test 2: With extended keep_alive
    # Modify the backend to use keep_alive
    from ollama_backend import OllamaChat
    original_generate = OllamaChat.generate

    def generate_with_keep_alive(self, messages, tools=None, stop_sequences=None, **kwargs):
        # Store original endpoint
        result = original_generate(self, messages, tools, stop_sequences, **kwargs)
        # Set keep_alive after generation
        try:
            requests.post(self.endpoint.replace('/chat', '/generate'), json={
                'model': self.model,
                'prompt': '',
                'keep_alive': '30m'
            })
        except:
            pass
        return result

    OllamaChat.generate = generate_with_keep_alive

    benchmark2 = DetailedBenchmark()
    benchmark2.run_benchmark(query, iterations=20, test_name="With keep_alive=30m")

    # Comparison
    print("\n" + "="*70)
    print("🔍 COMPARISON")
    print("="*70)
    times1 = [r['total_time'] for r in benchmark1.results]
    times2 = [r['total_time'] for r in benchmark2.results]

    print(f"Default avg:          {statistics.mean(times1):.2f}s ± {statistics.stdev(times1):.2f}s")
    print(f"With keep_alive avg:  {statistics.mean(times2):.2f}s ± {statistics.stdev(times2):.2f}s")
    print(f"Improvement:          {statistics.mean(times1) - statistics.mean(times2):.2f}s ({(1 - statistics.mean(times2)/statistics.mean(times1))*100:.1f}%)")
    print(f"{'='*70}\n")
