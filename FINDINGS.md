# Ollama DevOps Agent - Test Findings Summary

**Date:** 2025-10-23
**Project:** SmolAgents-based DevOps automation with local Ollama models

---

## Executive Summary

We tested two small language models (1.5-1.7B parameters) for DevOps tool-calling tasks. Results show **dramatic performance differences** between models, with Qwen3 1.7B achieving **70% average pass rate** while Qwen2.5-Coder 1.5B only achieved **21%**, despite being specifically trained for coding.

---

## Models Tested

### Model 1: Qwen3 1.7B (Baseline)
- **Size:** 1.7B parameters, ~1.4GB (Q4 quantization)
- **Type:** General-purpose chat model
- **Results:** 70% average pass rate (6/10 tests always passing)

### Model 2: Qwen2.5-Coder 1.5B Q6_K
- **Size:** 1.5B parameters, ~1.5GB (Q6_K quantization)
- **Type:** Code-specialized model
- **Results:** 21% average pass rate (0/10 tests always passing)

---

## Test Results Comparison

| Test ID | Test Name | Qwen3 1.7B | Qwen2.5-Coder 1.5B | Delta |
|---------|-----------|------------|---------------------|-------|
| 01 | read_env_var | 100% ✅ | 14% ❌ | -86% |
| 02 | read_multiple_env_vars | 100% ✅ | 0% ❌ | -100% |
| 03 | create_simple_file | 100% ✅ | 57% ⚠️ | -43% |
| 04 | create_file_from_env | 86% ✓ | 0% ❌ | -86% |
| 05 | read_existing_file | 100% ✅ | 29% ❌ | -71% |
| 06 | run_simple_command | 57% ⚠️ | 14% ❌ | -43% |
| 07 | list_files | 100% ✅ | 29% ❌ | -71% |
| 08 | multi_step_task | 57% ⚠️ | 0% ❌ | -57% |
| 09 | create_dockerfile | 0% ❌ | 29% ❌ | +29% |
| 10 | handle_missing_env | 100% ✅ | 43% ⚠️ | -57% |
| **AVERAGE** | **All Tests** | **70%** | **21%** | **-49%** |

**Legend:**
- ✅ Always passing (100%)
- ✓ Mostly passing (70-99%)
- ⚠️ Inconsistent (30-70%)
- ❌ Mostly/always failing (0-30%)

---

## Key Findings

### 1. Tool Calling Format Matters Critically

**Problem Discovered:** Qwen models use different tool calling formats:
- **Qwen3:** Uses QWEN's native XML `<tool_call>` format
- **Qwen2.5-Coder:** May expect different format (function calling style)

**Impact:** Qwen2.5-Coder failed to properly parse/generate tool calls in our XML-based system.

### 2. Role Mapping Bug (Fixed)

**Issue:** SmolAgents' `MessageRole.TOOL_RESPONSE` was being sent as literal string instead of mapped to `"tool"` role that QWEN expects.

**Fix Applied (agent.py:104-108):**
```python
role_str = str(role).split(".")[-1].lower()
if role_str == "tool_response":
    role_str = "tool"  # QWEN expects "tool" for tool responses
```

**Impact:** Improved Qwen3 1.7B from 40% → 70% pass rate.

### 3. Tool Naming Impact

**Experiment:** Renamed `run_command` → `bash`

**Results:**
- ✅ Test 07 (list_files) started passing consistently
- ❌ Introduced regressions in tests 08 & 09
- **Conclusion:** More familiar names help, but can confuse value-passing logic

### 4. Model-Specific Reliability Patterns

**Qwen3 1.7B Reliability:**
- **Always reliable (100%):** 6 tests - env vars, file ops, bash commands
- **Inconsistent (57%):** 2 tests - bash output reporting, multi-step value reuse
- **Always broken (0%):** 1 test - dockerfile with explicit get_env requirement

**Qwen2.5-Coder 1.5B Reliability:**
- **Always reliable (100%):** 0 tests
- **Inconsistent (43-57%):** 2 tests
- **Mostly/always broken (0-29%):** 8 tests
- **Completely broken (0%):** 3 tests (multi-step tasks, env variable operations)

### 5. Value Reuse Problem

**Symptom:** Model writes variable NAME instead of VALUE
```python
# Expected: content="myapp" (the value)
# Actual: content="APP_NAME" (the variable name)
```

**Affected Tests:**
- Test 04: create_file_from_env (86% pass rate on Qwen3, 0% on Qwen2.5)
- Test 08: multi_step_task (57% pass rate on Qwen3, 0% on Qwen2.5)

**Root Cause:** Model doesn't consistently track that tool response values should replace placeholders.

### 6. Bash Output Reporting Issue

**Test 06 (run_simple_command):**
- Model calls `bash` tool correctly
- Receives output "Hello DevOps"
- But returns generic "Task completed" instead of including the output

**Pattern:** Model treats bash as side effect, not as data source for final answer.

---

## Technical Implementation Details

### Architecture

```
User Query
    ↓
SmolAgents ToolCallingAgent
    ↓
OllamaChat Backend (ollama_backend.py)
    ↓
Ollama API (localhost:11434)
    ↓
QWEN Model (qwen3:1.7b or qwen2.5-coder:1.5b)
```

### Key Components

**1. ollama_backend.py**
- Custom SmolAgents backend
- Role mapping: `MessageRole.TOOL_RESPONSE` → `"tool"`
- Tool list building with system context
- XML `<tool_call>` parsing

**2. agent.py**
- Monkey-patches SmolAgents' system prompt
- Custom tool response formatting: `"The value is: {value}"`
- Tools: `read_file`, `write_file`, `bash`, `get_env`

**3. STRICT_INSTRUCTIONS**
- Emphasizes one-tool-at-a-time execution
- Prohibits calling `final_answer` with other tools
- Requires using ACTUAL values from tool responses

### System Prompt Strategy

**Approach:** Minimal, directive-based prompting
```
1. Use ONLY <tool_call> XML tags
2. Call ONE tool at a time, then WAIT
3. NEVER call final_answer together with other tools
4. Use ACTUAL values from tool responses
```

**Trade-off:** Simple prompts work for Qwen3 but not Qwen2.5-Coder.

---

## Variability Analysis

### Test Consistency Categories

**Qwen3 1.7B:**
- **Deterministic Success:** 6 tests always pass
- **Flaky:** 2 tests (57% pass rate) - inconsistent value handling
- **Deterministic Failure:** 1 test always fails

**Qwen2.5-Coder 1.5B:**
- **Deterministic Success:** 0 tests
- **Flaky:** 2 tests (43-57% pass rate)
- **Deterministic Failure:** 8 tests

### Interesting Pattern (Qwen3 Test 08)

```
Run: 1  2  3  4  5  6  7
     ✓  ✗  ✓  ✗  ✓  ✓  ✗
```

**Alternating pattern suggests:**
- Possible temperature/sampling effects (even at deterministic settings)
- Context sensitivity
- State dependency between runs

---

## Tool-Specific Performance

### Best Performing Tools (Qwen3 1.7B)

1. **get_env** - 100% reliable for single reads
2. **write_file** - 100% reliable for simple writes
3. **read_file** - 100% reliable
4. **bash** - 100% reliable for execution, 57% for output reporting

### Problematic Patterns

1. **Multi-step value passing:** Inconsistent (57% success)
2. **Bash output in final_answer:** Unreliable (57% success)
3. **Explicit get_env before write:** Model prefers shortcuts (0% on test 09)

---

## Conclusions

### What Works

✅ **Qwen3 1.7B is surprisingly capable** for basic DevOps tasks
✅ **Role mapping fix was critical** (40% → 70% improvement)
✅ **Simple, directive prompts** work for small models
✅ **Tool naming matters** (bash > run_command)

### What Doesn't Work

❌ **Qwen2.5-Coder 1.5B** performs worse despite code specialization
❌ **Tool call format mismatch** is a major blocker
❌ **Value reuse across steps** is inconsistent
❌ **Bash output reporting** needs explicit instruction

### Surprising Discovery

**Model size alone doesn't predict performance.** A 1.7B general model (Qwen3) vastly outperforms a 1.5B code-specialized model (Qwen2.5-Coder) when the tool-calling format matches.

---

## Recommendations

### Immediate Actions

1. **Stick with Qwen3 1.7B** for now - proven 70% reliability
2. **Investigate Qwen2.5-Coder's expected tool format** - may need different XML schema
3. **Fix Test 09** - consider if test expectation is too strict
4. **Enhance bash tool description** - emphasize output reporting

### Next Steps

1. **Try Qwen2.5-Coder 7B** (larger model may handle format better)
2. **Test with function calling format** instead of XML
3. **Add explicit value-tracking instructions** to reduce Test 08 flakiness
4. **Consider fine-tuning** on tool-calling examples

### For Production Use

**Minimum requirements identified:**
- ✅ 70%+ pass rate acceptable for assisted workflows
- ⚠️ 57% flaky tests need human oversight
- ❌ 21% pass rate insufficient for automation

**Model selection criteria:**
1. Tool calling format compatibility > model size
2. General chat models may outperform specialized models
3. Test with actual workload before deployment

---

## Repository State

### Current Configuration

**Files modified:**
- `ollama_backend.py` - Role mapping fix (lines 104-110)
- `agent.py` - Tool renamed `run_command` → `bash`
- `tests/config.json` - Model set to Qwen2.5-Coder 1.5B
- `tests/variability_test.py` - New variability testing framework

**Test coverage:**
- 10 test cases covering env vars, file ops, bash commands, multi-step tasks
- Variability testing: 7 runs per model
- Total test time: ~30-40 minutes per model

### Key Metrics

**Qwen3 1.7B:**
- Average pass rate: 70%
- Variability range: 67-71%
- Reliable tests: 6/10
- Total test time: 290s per run

**Qwen2.5-Coder 1.5B:**
- Average pass rate: 21%
- Variability range: 0-40%
- Reliable tests: 0/10
- Total test time: 263s per run

---

## Future Research Questions

1. **Why does Qwen2.5-Coder perform so poorly?**
   - Wrong tool call format?
   - Different prompt requirements?
   - Q6_K quantization artifacts?

2. **Can we reach 90%+ reliability with 1.7B models?**
   - Better prompting?
   - Fine-tuning?
   - Different model architecture?

3. **What's the minimum model size for production?**
   - Is 7B the sweet spot?
   - Can we optimize 1.7B further?

4. **Is deterministic tool calling possible?**
   - Test 08's alternating pattern suggests non-determinism
   - Temperature=0 doesn't guarantee consistency

---

## Contact & Credits

**Project:** ollama_devops
**Framework:** SmolAgents + Ollama
**Models:** Alibaba Cloud (Qwen3, Qwen2.5-Coder)
**Testing:** 7x10 variability matrix (140 test executions)

**Key insight:** Small model success depends more on **format compatibility** than **model specialization**.
