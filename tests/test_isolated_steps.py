#!/usr/bin/env python3
"""
Test if the model can handle steps better when isolated.
"""
from ollama_backend import OllamaChat
from smolagents import ChatMessage

model = OllamaChat(model='qwen3:1.7b')

print("=" * 60)
print("HYPOTHESIS: Model works better with isolated single-step prompts")
print("=" * 60)

# Test 1: Simple value echo
print("\n[TEST 1] Can it echo a value it's given?")
print("-" * 60)
msg = model.generate([
    ChatMessage(role='user', content='I got the value "testuser" from a tool. Please repeat this value back to me.')
])
print(f"Response: {msg.content[:150]}")
print(f"✓ PASS" if "testuser" in msg.content.lower() else "✗ FAIL - didn't include 'testuser'")

# Test 2: Value substitution
print("\n[TEST 2] Can it use a given value in a template?")
print("-" * 60)
msg2 = model.generate([
    ChatMessage(role='user', content='The value is "testuser". Fill in this template: "User: <VALUE>"')
])
print(f"Response: {msg2.content[:150]}")
print(f"✓ PASS" if "testuser" in msg2.content.lower() else "✗ FAIL - didn't substitute value")

# Test 3: Create tool call JSON with given value
print("\n[TEST 3] Can it create correct JSON with a given value?")
print("-" * 60)
msg3 = model.generate([
    ChatMessage(role='user', content='Create a JSON object for write_file tool: path="config.txt", content="User: testuser"')
])
print(f"Response: {msg3.content[:200]}")
has_json = '{"path"' in msg3.content or "{\"path\"" in msg3.content
has_value = "testuser" in msg3.content.lower()
print(f"✓ PASS" if (has_json and has_value) else f"✗ FAIL - JSON:{has_json}, Value:{has_value}")

print("\n" + "=" * 60)
print("CONCLUSION:")
print("=" * 60)
