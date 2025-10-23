# openrouter_backend.py
import json, re, uuid, os
import requests
from smolagents.models import ChatMessage
import platform
import shutil

STRICT_INSTRUCTIONS = """
You are a DevOps automation agent that executes tasks step-by-step using tools.

CRITICAL RULES:
1. Respond with ONLY a single JSON tool call per message
2. Use format: {"name": "tool_name", "arguments": {"arg1": "value1", "arg2": "value2"}}
3. Call ONE tool at a time, then WAIT for the response
4. NEVER call final_answer together with other tools - it must be alone
5. When you receive tool responses like "The value is: testuser", use that EXACT value in your answer
6. ALWAYS include the actual value returned by tools in your final_answer
7. Never include natural language outside tool calls
8. If you encounter an error, try a different approach
9. Do NOT repeat the same failing tool call twice with identical arguments

TOOL CALL FORMAT:
{"name": "tool_name", "arguments": {"arg1": "value1", "arg2": "value2"}}

EXAMPLES:

Example 1 - Getting an environment variable:
Step 1 - Call tool:
{"name": "get_env", "arguments": {"key": "DOCKER_USER"}}

Step 2 - You receive: "The value is: testuser"
Step 3 - Answer with the ACTUAL value you received:
{"name": "final_answer", "arguments": {"answer": "testuser"}}

Example 2 - Using returned value in another tool:
Step 1 - Call tool:
{"name": "get_env", "arguments": {"key": "APP_NAME"}}

Step 2 - You receive: "The value is: myapp"
Step 3 - Use that exact value:
{"name": "write_file", "arguments": {"path": "config.txt", "content": "App: myapp"}}

Example 3 - Completing a task:
{"name": "final_answer", "arguments": {"answer": "Task completed successfully"}}

CRITICAL REMINDERS:
- Always use ACTUAL values from tool responses, not variable names
- Include the returned value in your final_answer
- One tool call per message only
- Wait for the response before calling the next tool
"""


class OpenRouterChat:
    """
    SmolAgents-compatible OpenRouter backend.
    Uses OpenRouter API instead of local Ollama.
    """

    def __init__(self, model="qwen/qwen-turbo",
                 api_key=None):
        self.model = model
        self.api_key = api_key or os.environ.get("OPEN_ROUTER_KEY")
        if not self.api_key:
            raise ValueError("OpenRouter API key required. Set OPEN_ROUTER_KEY environment variable.")
        self.endpoint = "https://openrouter.ai/api/v1/chat/completions"
        self.name = "OpenRouterChat"
        self.supports_streaming = False

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _serialize_messages(self, messages):
        """Flatten SmolAgents ChatMessages into OpenRouter-compatible format."""
        serialized = []
        for m in messages:
            # Determine role
            role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else "user")

            # Extract content
            raw_content = getattr(m, "content", None) or (
                m.get("content") if isinstance(m, dict) else str(m)
            )

            # Flatten [{"type":"text","text":"..."}] → "..."
            if isinstance(raw_content, list):
                content_parts = []
                for c in raw_content:
                    if isinstance(c, dict) and "text" in c:
                        content_parts.append(c["text"])
                    else:
                        content_parts.append(str(c))
                content = "\n".join(content_parts)
            else:
                content = str(raw_content)

            # Convert role to string and normalize
            role_str = str(role).split(".")[-1].lower()  # MessageRole.TOOL_RESPONSE → "tool_response"

            # Map SmolAgents roles to OpenRouter's expected roles
            if role_str == "tool_response":
                role_str = "user"  # OpenRouter doesn't have "tool" role, use user for tool responses

            serialized.append({"role": role_str, "content": content})
        return serialized

    def _build_tool_list(self, tools):
        """
        Build a rich system prompt section describing tools and environment.
        """
        # 1️⃣ System context info
        system_info = [
            f"Operating system: {platform.system()} {platform.release()}",
            f"Python version: {platform.python_version()}",
            f"Docker available: {'yes' if shutil.which('docker') else 'no'}",
            f"Shell: {os.getenv('SHELL', 'unknown')}",
        ]
        system_section = "System information:\n- " + "\n- ".join(system_info) + "\n"

        # 2️⃣ Tool definitions
        lines = ["Available tools (name(args): description):"]
        tool_objs = tools.values() if isinstance(tools, dict) else tools
        for t in tool_objs:
            if getattr(t, "name", "") == "final_answer":
                continue  # keep final_answer separate
            name = getattr(t, "name", getattr(t, "__name__", "unknown_tool"))
            desc = (getattr(t, "description", None) or getattr(t, "__doc__", "") or "No description.").strip()
            if hasattr(t, "inputs") and t.inputs:
                arg_lines = []
                for arg_name, arg_schema in t.inputs.items():
                    arg_type = arg_schema.get("type", "string")
                    arg_desc = arg_schema.get("description", "")
                    arg_lines.append(f"  - {arg_name}: {arg_type} — {arg_desc}")
                args_section = "\n".join(arg_lines)
            else:
                args_section = "  (no arguments)"
            lines.append(f"- {name}:\n{args_section}\n  Description: {desc}")

        # 3️⃣ Tool usage examples (plain JSON format for OpenRouter)
        examples = [
            "",
            "Example tool calls:",
            '{"name": "get_env", "arguments": {"key": "DOCKER_USER"}}',
            '{"name": "bash", "arguments": {"command": "ls *.txt"}}',
            '{"name": "write_file", "arguments": {"path": "Dockerfile", "content": "FROM alpine\\nCMD echo hello"}}',
            "",
            "When you are done, finalize with:",
            '{"name": "final_answer", "arguments": {"answer": "Task completed"}}',
        ]

        return "\n".join([system_section] + lines + examples)

    # -------------------------------------------------------------------------
    # Core API
    # -------------------------------------------------------------------------

    def generate(self, messages, tools=None, stop_sequences=None, **kwargs):
        """
        Generate a single assistant message using OpenRouter API.
        """

        tools = tools or kwargs.get("tools") or getattr(self, "tools", [])

        # 1️⃣ Convert messages into OpenRouter format
        flattened_msgs = self._serialize_messages(messages)

        # 2️⃣ Patch the system prompt
        for msg in flattened_msgs:
            role_str = str(msg.get("role", "")).split(".")[-1].lower()
            msg["role"] = role_str

            if role_str == "system":
                msg["content"] = (
                    STRICT_INSTRUCTIONS.strip()
                    + "\n\nSystem information:\n"
                    + self._build_tool_list(tools or [])
                )

        # 3️⃣ POST to OpenRouter
        payload = {
            "model": self.model,
            "messages": flattened_msgs,
            "temperature": 0,  # Deterministic
            "max_tokens": 500,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # Debug: print what is sent
        print("\n=== PAYLOAD SENT TO OPENROUTER (trimmed) ===")
        print(f"Model: {payload['model']}")
        print(f"Messages: {len(flattened_msgs)}")
        print(f"Last user message: {flattened_msgs[-1]['content'][:100] if flattened_msgs else 'N/A'}...\n")

        try:
            resp = requests.post(self.endpoint, json=payload, headers=headers, timeout=120)
        except requests.Timeout:
            raise RuntimeError("OpenRouter request timeout (120s)")

        if not resp.ok:
            error_text = resp.text
            try:
                error_json = resp.json()
                error_text = error_json.get("error", {}).get("message", error_text)
            except:
                pass
            raise RuntimeError(f"OpenRouter returned {resp.status_code}: {error_text}")

        data = resp.json()

        print("\n🟩 === [RECV] OpenRouter Response ===")
        print(json.dumps(data, indent=2, ensure_ascii=False)[:500])

        # 4️⃣ Extract assistant content
        content = ""
        if "choices" in data and len(data["choices"]) > 0:
            content = data["choices"][0]["message"].get("content", "").strip()
        else:
            content = str(data)

        # 5️⃣ Return a proper ChatMessage (SmolAgents expects this type)
        return ChatMessage(role="assistant", content=content)

    # -------------------------------------------------------------------------
    # Tool call parsing
    # -------------------------------------------------------------------------

    def parse_tool_calls(self, message):
        """
        Parse model output in plain JSON format.
        OpenRouter models return clean JSON: {"name": "tool_name", "arguments": {...}}
        """
        # --- Universal import across SmolAgents versions ---
        try:
            from smolagents.types import ChatToolCall, FunctionCall
        except ImportError:
            try:
                from smolagents.protocol import ChatToolCall, FunctionCall
            except ImportError:
                try:
                    from smolagents.schema import ChatToolCall, FunctionCall
                except ImportError:
                    from dataclasses import dataclass
                    @dataclass
                    class FunctionCall:
                        name: str
                        arguments: dict
                    @dataclass
                    class ChatToolCall:
                        id: str
                        function: FunctionCall

        text = getattr(message, "content", str(message))
        calls = []

        print(f"\n🔍 [parse_tool_calls] Parsing message content: {text[:200]}")

        # Parse plain JSON tool calls (OpenRouter's native format)
        # Pattern: {"name": "...", "arguments": {...}}
        for match in re.finditer(r'\{[^{}]*"name"[^{}]*"arguments"[^{}]*\}', text):
            try:
                tool_data = json.loads(match.group())
                name = tool_data.get("name", "unknown")
                args = tool_data.get("arguments", {})

                print(f"   ✓ Found tool call: {name}")

                func = FunctionCall(name=name, arguments=args)

                try:
                    call = ChatToolCall(id=str(uuid.uuid4()), function=func)
                except TypeError:
                    call = ChatToolCall(function=func)

                calls.append(call)
            except json.JSONDecodeError as e:
                print(f"⚠️  WARNING: Failed to parse tool call JSON: {e}")
                continue

        print(f"   📊 Total calls found: {len(calls)}")

        # 🛡️ SAFETY: If final_answer is present with other tools, remove it
        has_final_answer = any(call.function.name == "final_answer" for call in calls)
        has_other_tools = any(call.function.name != "final_answer" for call in calls)

        if has_final_answer and has_other_tools:
            print("\n⚠️  WARNING: Model tried to call final_answer with other tools. Stripping final_answer to prevent loop.")
            calls = [c for c in calls if c.function.name != "final_answer"]

        if hasattr(message, "__dict__"):
            message.tool_calls = calls
        return message
