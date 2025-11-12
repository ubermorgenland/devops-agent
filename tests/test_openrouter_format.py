#!/usr/bin/env python3
"""
Test if OpenRouter models understand XML tool call format like Ollama does.
"""
import json
import requests
import os

OPENROUTER_API_KEY = os.environ.get("OPEN_ROUTER_KEY")
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM_PROMPT = """You are a DevOps automation agent. You have access to these tools:

1. get_env(key: str) - Read an environment variable
2. read_file(path: str) - Read a file
3. write_file(path: str, content: str) - Write to a file
4. bash(command: str) - Execute a bash command

RESPOND WITH ONLY VALID TOOL CALLS IN THIS EXACT FORMAT:
<tool_call>
{"name": "tool_name", "arguments": {"arg": "value"}}
</tool_call>

RULES:
- One tool call per response only
- Wait for response before calling next tool
- Use actual values from responses in next calls
- Always include tool calls - NO text outside the tags"""

def test_model(model_name: str):
    """Test if model understands XML format."""
    print(f"\n{'='*70}")
    print(f"Testing {model_name}...")
    print(f"{'='*70}")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "What is the value of the DOCKER_USER environment variable?"}
    ]

    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": 0,
        "max_tokens": 300,
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(OPENROUTER_ENDPOINT, json=payload, headers=headers, timeout=60)

        if response.status_code != 200:
            print(f"Error {response.status_code}: {response.text}")
            return None

        data = response.json()
        
        # Print full response
        print("\nFull OpenRouter Response:")
        print(json.dumps(data, indent=2))
        
        assistant_message = data["choices"][0]["message"]["content"]

        print(f"\nAssistant message content: {assistant_message}")

        # Check format
        if "<tool_call>" in assistant_message:
            print("✓ Model supports XML format")
            return "xml"
        elif '{"name":' in assistant_message:
            print("✓ Model returns plain JSON")
            return "json"
        else:
            print("✗ Unexpected format")
            return None

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    if not OPENROUTER_API_KEY:
        print("Error: OPEN_ROUTER_KEY not set")
        exit(1)

    models = ["qwen/qwen3-4b:free", "qwen/qwen3-coder:free"]

    for model in models:
        test_model(model)
