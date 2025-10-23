# openrouter_backend.py
import json, re, uuid, os
import requests
from smolagents.models import ChatMessage
import platform
import shutil
import time

STRICT_INSTRUCTIONS = """
You are a DevOps automation agent that executes tasks step-by-step using tools.

CRITICAL RULES:
1. Use ONLY <tool_call> XML tags for tool calls (see examples below)
2. Call ONE tool at a time, then WAIT for the response
3. NEVER call final_answer together with other tools - it must be alone
4. When you receive tool responses, use the ACTUAL values in your next tool calls
5. Never include natural language outside tool calls
6. If you encounter an error, try a different approach
7. Do NOT repeat the same failing tool call twice with identical arguments

TOOL CALL FORMAT:
<tool_call>
{"name": "tool_name", "arguments": {"arg1": "value1", "arg2": "value2"}}
</tool_call>

EXAMPLES:

Example 1 - Getting a value and using it:
Step 1 - Call tool:
<tool_call>
{"name": "get_env", "arguments": {"key": "DOCKER_USER"}}
</tool_call>

Step 2 - After receiving "The value is: testuser", use that value:
<tool_call>
{"name": "final_answer", "arguments": {"answer": "testuser"}}
</tool_call>

Example 2 - Using value in another tool:
Step 1:
<tool_call>
{"name": "get_env", "arguments": {"key": "APP_NAME"}}
</tool_call>

Step 2 - After receiving "The value is: myapp":
<tool_call>
{"name": "write_file", "arguments": {"path": "config.txt", "content": "App: myapp"}}
</tool_call>

Example 3 - Completing task:
<tool_call>
{"name": "final_answer", "arguments": {"answer": "Task completed"}}
</tool_call>

IMPORTANT:
- Call tools ONE AT A TIME
- WAIT for response before calling next tool
- Use ACTUAL values from responses (e.g., "testuser"), not placeholders
- Arguments must be valid JSON (no f-strings, no variables)
"""


class OpenRouterChat:
    """
    SmolAgents-compatible OpenRouter backend.
    Uses OpenRouter API instead of local Ollama.
    """

    def __init__(self, model="qwen/qwen-turbo",
                 api_key=None,
                 rate_limit_delay=3.0):
        self.model = model
        self.api_key = api_key or os.environ.get("OPEN_ROUTER_KEY")
        if not self.api_key:
            raise ValueError("OpenRouter API key required. Set OPEN_ROUTER_KEY environment variable.")
        self.endpoint = "https://openrouter.ai/api/v1/chat/completions"
        self.name = "OpenRouterChat"
        self.supports_streaming = False
        self.rate_limit_delay = rate_limit_delay  # Delay between requests in seconds (20/min = 3s)
        self.last_request_time = 0

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
        Generate a single assistant message using OpenRouter API with exponential backoff retry.
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

        # 🛡️ RATE LIMITING: Respect OpenRouter's limits
        # qwen3-coder needs stricter rate limiting (appears to have tighter limits)
        # qwen3-8b can handle faster rates
        rate_limit_enabled = self.rate_limit_delay > 0
        if rate_limit_enabled:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.rate_limit_delay:
                sleep_time = self.rate_limit_delay - elapsed
                # Only print on first request to avoid spam
                if self.last_request_time > 0 and sleep_time > 0.1:
                    pass  # Silently rate limit
                time.sleep(sleep_time)

        # 🔄 EXPONENTIAL BACKOFF: Retry on 429 (rate limit) errors
        max_retries = 5
        base_delay = 1.0  # Start with 1 second
        max_delay = 60.0  # Cap at 60 seconds

        for attempt in range(max_retries):
            try:
                self.last_request_time = time.time()
                resp = requests.post(self.endpoint, json=payload, headers=headers, timeout=120)
            except requests.Timeout:
                raise RuntimeError("OpenRouter request timeout (120s)")

            # Handle 429 (Too Many Requests) with exponential backoff
            if resp.status_code == 429:
                if attempt < max_retries - 1:
                    # Calculate exponential backoff delay
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    print(f"⏳ Rate limited (429). Retry {attempt + 1}/{max_retries} in {delay:.1f}s...")
                    time.sleep(delay)
                    continue
                else:
                    # Max retries exceeded
                    error_text = resp.text
                    try:
                        error_json = resp.json()
                        error_text = error_json.get("error", {}).get("message", error_text)
                    except:
                        pass
                    raise RuntimeError(f"OpenRouter returned {resp.status_code}: {error_text} (after {max_retries} retries)")

            # Handle other errors
            if not resp.ok:
                error_text = resp.text
                try:
                    error_json = resp.json()
                    error_text = error_json.get("error", {}).get("message", error_text)
                except:
                    pass
                raise RuntimeError(f"OpenRouter returned {resp.status_code}: {error_text}")

            # Success - break out of retry loop
            break

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
        Parse model output in XML format (same as Ollama backend).
        <tool_call>
        {"name": "tool_name", "arguments": {"arg": "value"}}
        </tool_call>
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

        # Try parsing XML <tool_call> tags (our standardized format)
        for match in re.finditer(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", text, re.DOTALL):
            try:
                tool_data = json.loads(match.group(1))
                name = tool_data.get("name", "unknown")
                args = tool_data.get("arguments", {})

                func = FunctionCall(name=name, arguments=args)

                try:
                    call = ChatToolCall(id=str(uuid.uuid4()), function=func)
                except TypeError:
                    call = ChatToolCall(function=func)

                calls.append(call)
            except json.JSONDecodeError as e:
                print(f"⚠️  WARNING: Failed to parse tool call JSON: {e}")
                continue

        # If no XML tags found, try markdown JSON blocks (fallback)
        if not calls:
            for match in re.finditer(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL):
                try:
                    tool_data = json.loads(match.group(1))
                    if "name" in tool_data and "arguments" in tool_data:
                        name = tool_data.get("name")
                        args = tool_data.get("arguments", {})

                        func = FunctionCall(name=name, arguments=args)

                        try:
                            call = ChatToolCall(id=str(uuid.uuid4()), function=func)
                        except TypeError:
                            call = ChatToolCall(function=func)

                        calls.append(call)
                except json.JSONDecodeError:
                    continue

        # 🛡️ SAFETY: If final_answer is present with other tools, remove it
        has_final_answer = any(call.function.name == "final_answer" for call in calls)
        has_other_tools = any(call.function.name != "final_answer" for call in calls)

        if has_final_answer and has_other_tools:
            print("\n⚠️  WARNING: Model tried to call final_answer with other tools. Stripping final_answer to prevent loop.")
            calls = [c for c in calls if c.function.name != "final_answer"]

        if hasattr(message, "__dict__"):
            message.tool_calls = calls
        return message
