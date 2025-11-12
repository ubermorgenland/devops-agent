#!/usr/bin/env python3
"""
Direct OpenRouter API test - simple exploration of tool calling format.
Tests a single task with different Qwen models via OpenRouter.
"""
import json
import requests
import os

# OpenRouter API setup
OPENROUTER_API_KEY = os.environ.get("OPEN_ROUTER_KEY")
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

# Test models - Qwen variants in different sizes
MODELS = [
    "qwen/qwen-32b-vision",           # Larger baseline
    "qwen/qwen2.5-32b-instruct",      # Code instruction tuned
    "qwen/qwen-turbo",                # Smaller, faster
    "deepseek/deepseek-r1-0528-qwen3-8b",  # Your linked model
]

# Simple system prompt with tool definitions
SYSTEM_PROMPT = """You are a DevOps automation agent. You have access to these tools:

1. get_env(key: str) - Read an environment variable
2. read_file(path: str) - Read a file
3. write_file(path: str, content: str) - Write to a file
4. bash(command: str) - Execute a bash command

You MUST respond with JSON tool calls in this format ONLY:
{"name": "tool_name", "arguments": {"arg": "value"}}

After using a tool, wait for the response and use the value returned.
When done, call: {"name": "final_answer", "arguments": {"answer": "your answer"}}

Use tools ONE AT A TIME. Do not mix multiple tool calls in one response."""

def test_model(model_name: str, test_instruction: str):
    """Test a single model with the given instruction."""
    print(f"\n{'='*70}")
    print(f"Testing model: {model_name}")
    print(f"{'='*70}")

    # Set up environment for the test
    test_env = {"DOCKER_USER": "testuser"}

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": test_instruction
        }
    ]

    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0,  # Deterministic
        "max_tokens": 500,
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        print(f"Sending request to {OPENROUTER_ENDPOINT}...")
        response = requests.post(OPENROUTER_ENDPOINT, json=payload, headers=headers, timeout=60)

        if response.status_code != 200:
            print(f"❌ Error {response.status_code}: {response.text}")
            return None

        data = response.json()

        # Extract assistant response
        if "choices" in data and len(data["choices"]) > 0:
            assistant_message = data["choices"][0]["message"]["content"]
            print(f"\n✅ Model response:")
            print(assistant_message)

            # Try to parse tool calls
            try:
                # Check for JSON tool calls
                import re
                json_matches = re.findall(r'\{"name":\s*"[^"]+",\s*"arguments":', assistant_message)
                if json_matches:
                    print(f"\n✓ Found {len(json_matches)} potential tool call(s)")
                    # Extract full JSON objects
                    for match in re.finditer(r'\{[^{}]*"name"[^{}]*"arguments"[^{}]*\}', assistant_message):
                        try:
                            tool_call = json.loads(match.group())
                            print(f"  Tool: {tool_call.get('name')}")
                            print(f"  Args: {tool_call.get('arguments')}")
                        except json.JSONDecodeError:
                            pass
                else:
                    print("\n⚠️  No standard JSON tool calls found in response")
            except Exception as e:
                print(f"⚠️  Error parsing tool calls: {e}")

            return {
                "model": model_name,
                "response": assistant_message,
                "status": "success"
            }
        else:
            print("❌ No choices in response")
            return None

    except requests.Timeout:
        print("❌ Request timeout")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def main():
    """Run tests."""
    if not OPENROUTER_API_KEY:
        print("Error: OPEN_ROUTER_KEY environment variable not set")
        return

    # Test instruction from test case 01: read_env_var
    test_instruction = "What is the value of the DOCKER_USER environment variable?"

    results = []
    for model in MODELS:
        result = test_model(model, test_instruction)
        if result:
            results.append(result)

    # Summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Tested {len(results)}/{len(MODELS)} models successfully")
    for r in results:
        print(f"✓ {r['model']}")

if __name__ == "__main__":
    main()
