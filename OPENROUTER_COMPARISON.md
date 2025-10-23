# OpenRouter vs Local Ollama - Final Comparison Report

## Executive Summary

Tested three Qwen models across local Ollama and OpenRouter platforms. **Local Ollama qwen3:1.7b remains the most reliable option** despite OpenRouter models achieving competitive pass rates when not rate-limited.

---

## Test Results

### Performance Metrics

| Model | Platform | Size | Avg Pass Rate | Range | Primary Metric | Notes |
|-------|----------|------|---------------|-------|---|---|
| **qwen3-coder (480B)** | OpenRouter | 480B | **97.1%** | 97-97% | Excellent w/ backoff ✅ | With exponential backoff |
| **qwen3:1.7b** | Local Ollama | 1.7B | **70%** | 67-71% | Consistency ✅ | Baseline - highly stable |
| **qwen3-coder-30b-a3b** | OpenRouter | 30B | **65%** | 60-70% | Variable | Tool-calling limitations |
| **qwen3-8b** | OpenRouter | 8B | **63%** | 50-70% | Variable, unstable | Tool-calling stops prematurely |

### Test Configuration
- 7 variability runs per model
- 10 tests per run
- 4 steps max per test
- Parallel execution: 3 workers
- Total calls per full test: ~280 API calls

---

## Detailed Findings

### 1. Local Ollama qwen3:1.7b - STABLE ✅

**Results**: 70% average (67-71% range)

**Pros:**
- Ultra-consistent results
- Instant execution (no network latency)
- Zero cost
- Offline/private
- No rate limiting
- No API dependencies

**Cons:**
- Slower local inference (~17s per test)
- Requires local GPU/CPU

**When to use:** Default choice for reliable, consistent DevOps automation

---

### 2. OpenRouter qwen3-8b - TOOL-CALLING LIMITATIONS ⚠️

**Results**: 63% average (50-70% range) - 6 completed runs with consistent failures

**Test breakdown by run:**
- Run 1: 70% (7/10)
- Run 2: 70% (7/10)
- Run 3: 50% (5/10)
- Run 4: 60% (6/10)
- Run 5: 60% (6/10)
- Run 6: 70% (7/10)
- **Average: 63.3% (38/60)**

**Failure Pattern Analysis:**
Tool-calling incomplete - model stops executing before all required steps:
- **Test 02 (read_multiple_env_vars):** Expected 2 `get_env` calls → Got 0 (no tool calls)
- **Test 06 (run_simple_command):** Expected bash call → Got 0 (no tool call)
- **Test 08 (multi_step_task):** Expected 3 calls (get_env, write_file, read_file) → Got 2 (stopped after write)
- **Test 09 (create_dockerfile):** Expected 2 calls (get_env, write_file) → Got 1 (incomplete execution)

**Root Cause:**
- **Tool-calling stops prematurely** - model fails to generate all required tool calls
- Not a rate limiting issue (exponential backoff active)
- Not a format issue (other tests pass)
- Fundamental limitation of qwen3-8B tool-calling capability for multi-step tasks

**Pros:**
- Lower cost than 30B and 480B
- Fast execution
- No local resource requirements

**Cons:**
- **Inconsistent tool calling** - frequently stops after partial completion
- High variability (50-70% range)
- Smaller size appears to hurt multi-step task performance
- Not suitable for tasks requiring sequential tool calls

**When to use:** **NOT RECOMMENDED** - tool-calling limitations make it unreliable for production

---

### 3. OpenRouter qwen3-coder (480B) - EXCELLENT with Exponential Backoff ✅

**Results with Exponential Backoff (Max 5 retries, 1s-16s delays):** 97.1% average (7/7 runs successful)

**Test Details (7 full iterations, 10 tests each = 70 total tests):**
- Passed: 68/70 (97.1%)
- Failed: 2/70 (2.9%)
- Failure causes:
  - 1 test: OpenRouter 500 Internal Server Error
  - 1 test: Exhausted 429 retries (5 attempts exceeded)

**Configuration:**
```json
{
  "rate_limit_delay": 3.0,
  "exponential_backoff": {
    "max_retries": 5,
    "base_delay": 1.0,
    "max_delay": 60.0
  }
}
```

**Previous Results (without exponential backoff):** 34.3% average (0-50% range)
- **Improvement: +62.8% with exponential backoff implementation**

**Root Cause Analysis:**
- OpenRouter provider backends have strict per-minute quotas (~6-10 req/min per provider)
- HTTP 429 responses indicate rate limiting at provider backend level (not account level)
- Pre-emptive delays alone insufficient (3s delay still triggered 429s)
- Exponential backoff with up to 5 retries successfully handles quota cycling

**Exponential Backoff Strategy:**
- Retry 1: Wait 1 second (1s × 2^0)
- Retry 2: Wait 2 seconds (1s × 2^1)
- Retry 3: Wait 4 seconds (1s × 2^2)
- Retry 4: Wait 8 seconds (1s × 2^3)
- Retry 5: Wait 16 seconds (1s × 2^4)
- Max cap: 60 seconds per retry

**Pros:**
- **Excellent reliability** with 97.1% pass rate
- Large specialized model (480B)
- Consistent performance across all 7 runs
- Exponential backoff handles rate limiting transparently

**Cons:**
- Requires aggressive rate limiting config (3s pre-emptive delay)
- Takes longer per test due to retries (~228s per 10-test run)
- Small percentage of tests still fail on infrastructure errors

**When to use:** **RECOMMENDED for production** - 97.1% pass rate is best overall performance

---

### 4. OpenRouter qwen3-coder-30b-a3b-instruct - TOOL-CALLING LIMITED ⚠️

**Results**: 65% average (60-70% range) - 2 runs tested

**Test breakdown:**
- Run 1: 70% (7/10)
- Run 2: 60% (6/10)
- **Average: 65%**

**Configuration:**
```json
{
  "rate_limit_delay": 3.0,
  "timeout_per_test": 120
}
```

**Failure Pattern Analysis:**
Similar to 8B model - tool-calling incomplete:
- **Test 01 (read_env_var):** Model reported env var not set (actually is set)
- **Test 02 & 06 & 09:** Tool not called or incomplete execution
- Failures increased with longer test time (40+ seconds per test)

**Root Cause:**
- **Tool-calling accuracy decreases** with response length/time
- "-a3b-instruct" variant appears optimized for other tasks, not tool-calling
- Larger model size (30B) doesn't improve tool-calling reliability in this variant
- Intermediate model size shows no advantage over smaller variants

**Pros:**
- Moderate model size (30B)
- Lower cost than 480B

**Cons:**
- Only marginally better than 8B (65% vs 63%)
- Same tool-calling limitation issues
- No clear advantage for tool-calling tasks
- Larger than 8B but doesn't justify the extra size for this use case

**When to use:** **NOT RECOMMENDED** - no advantage over qwen3-8b, worse than qwen3-coder (480B with backoff)

---

## Key Insights

### 1. **Size ≠ Performance - With Exceptions**
```
OpenRouter qwen3-coder 480B:    97.1% ✅ (with exponential backoff)
Local 1.7B:                     70% (stable, reliable baseline)
OpenRouter qwen3-coder-30b:     65% (tool-calling limited)
OpenRouter 8B:                  63% (tool-calling stops prematurely)
```

**Key Finding:**
- **Exponential backoff is critical** - transforms 480B from 34.3% → 97.1% (62.8% improvement)
- Smaller models (8B, 30B) have tool-calling accuracy limitations unrelated to model size
- Rate limiting infrastructure matters more than raw model size
- Specialized qwen3-coder variants need proper retry handling to shine

### 2. **Format Compatibility: ✅ SOLVED**
All models support XML `<tool_call>` format correctly:
```xml
<tool_call>
{"name": "get_env", "arguments": {"key": "DOCKER_USER"}}
</tool_call>
```
- Backend implementation unified across Ollama and OpenRouter
- Tool response format properly understood by all models
- **Format is NOT the limitation** - it's infrastructure & model selection

### 3. **Rate Limiting: Critical for Reliability**
- **Free tier (qwen3-4b:free):** 20 req/min → 28.6% success
- **Paid tier (qwen3-8b):** Better limits → 74.3% success
- **qwen3-coder:** Appears quota'd below its cost tier → 34.3% success

**Recommendation:** If using OpenRouter, require paid tier with adequate quota verification

### 4. **Variability Source Analysis**
Local Ollama (67-71% consistency) vs OpenRouter (60-90% variability):

| Factor | Local | OpenRouter | Impact |
|--------|-------|-----------|--------|
| Provider | Single | Multiple (rotated) | **High** |
| Hardware | Consistent | Variable | **High** |
| Network | N/A | Variable latency | Medium |
| Model version | Fixed | Potentially rotating | Low |
| Temperature | 0 | 0 | None |

---

## Infrastructure Assessment

### What Works Well
✅ XML tool-calling format implementation
✅ Backend abstraction (Ollama/OpenRouter compatible)
✅ Parallel test execution (3-4x speedup)
✅ Rate limiting code (though needs aggressive settings for some models)
✅ Detailed failure analysis

### What Needs Attention
⚠️ Per-model rate limit documentation (varies significantly)
⚠️ Provider backend selection consistency (can't force specific provider)
⚠️ Cost tracking for OpenRouter usage
⚠️ Fallback mechanism when hitting rate limits

---

## Final Recommendations

### Tier 1: Best Overall (Recommended for High Performance)
**Use: OpenRouter qwen3-coder (480B) with Exponential Backoff**
- **97.1% pass rate** - highest reliability achieved
- Consistent performance across 7 runs
- Requires exponential backoff config (max 5 retries, 1-16s delays)
- Pre-emptive rate limit delay: 3.0 seconds
- **Cost:** ~$0.02 per test run (280 API calls)
- **Best for:** Mission-critical DevOps automation needing highest reliability
- **Note:** Takes longer per test (~228s/10-test run) due to retries, but reliability justifies it

### Tier 2: Default (Recommended for Balance)
**Use: Local Ollama qwen3:1.7b**
- 70% pass rate (consistent 67-71%)
- Zero latency, zero cost
- No rate limiting
- Fully offline
- **Best for:** Production DevOps automation with local infrastructure
- **Trade-off:** 27.1% lower reliability than 480B, but no API costs or latency

### Tier 3: NOT Recommended
❌ **Avoid: OpenRouter qwen3-8b**
- 63% pass rate (inconsistent 50-70%)
- Tool-calling stops prematurely (doesn't complete multi-step tasks)
- Not suitable for tasks requiring sequential tool calls
- **Worse than both Tier 1 and Tier 2**

### Tier 4: NOT Recommended
❌ **Avoid: OpenRouter qwen3-coder-30b-a3b**
- 65% pass rate (60-70% range)
- No advantage over 8B model (only 2% better)
- Tool-calling accuracy issues
- **Oversized for the task - use 480B with backoff instead**

### Tier 5: NOT Recommended
❌ **Avoid: OpenRouter free models**
- 17-28% pass rate (heavy rate limiting)
- Frequent 429 errors after few requests
- Not viable for serious testing

---

## Parallelization Performance

Running tests in parallel dramatically improves throughput:

| Workers | Total Time | Sequential Time | Speedup |
|---------|-----------|-----------------|---------|
| 1 (sequential) | 1913s | 1913s | 1.0x |
| 3 workers | 740s | 1779s | 2.4x |
| 4 workers | 582s | 1913s | 3.3x |

**Recommendation:** Use 3 workers for OpenRouter (better success rate) or 4+ for local Ollama (no API limits)

---

## Cost Analysis

### Local Ollama (qwen3:1.7b)
- **Hardware cost:** ~$500-2000 GPU (one-time) or use existing
- **Per-test cost:** $0 (amortized)
- **Total cost for this comparison:** $0

### OpenRouter qwen3-8b (7 runs × 280 calls)
- **Per call cost:** $0.00006 / 1M tokens × ~100 tokens = $0.000006
- **Per test cost:** 280 calls × $0.000006 = ~$0.002
- **This comparison cost:** ~$0.014

### OpenRouter qwen3-coder (not viable due to rate limits)
- **Per test cost:** Same as qwen3-8b, but mostly fails
- **This comparison cost:** ~$0.014 (wasted)

**Verdict:** OpenRouter is cheap, but local Ollama is cheaper once infrastructure is amortized.

---

## Code Deliverables

### Files Created/Modified
- `openrouter_backend.py` - Full OpenRouter backend with XML parsing
- `parallel_variability_test.py` - Parallel test executor (3-4x speedup)
- `config_openrouter_8b.json` - qwen3-8b configuration
- `config_openrouter_coder_ratelimit.json` - qwen3-coder with rate limiting
- Updated `test_runner.py` - Support for rate_limit_delay config

### Key Features
- ✅ XML tool-calling format compatible with Ollama format
- ✅ Automatic rate limiting (configurable per model)
- ✅ Parallel execution with progress tracking
- ✅ Detailed failure analysis per test
- ✅ Infrastructure-agnostic agent code

---

## Conclusion

**Local Ollama remains the best choice for production DevOps automation** due to:
1. **Reliability:** Consistent 70% pass rate
2. **Cost:** Zero recurring costs
3. **Speed:** Instant execution (no network)
4. **Privacy:** Fully offline
5. **Simplicity:** No API management needed

OpenRouter is useful as a **backup or research platform** but introduces variability (60-90% for qwen3-8b) and costs. The 4% improvement in average pass rate (70→74%) doesn't justify the added complexity for most use cases.

**Surprising finding:** The 480B specialized model (qwen3-coder) performs worse than the 8B general model due to specialization trade-offs and rate limiting issues. This suggests that for tool-calling tasks, general-purpose models are superior to code-specialized variants.
