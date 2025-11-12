# ollama_backend.py
import json, re, uuid, os
import requests
from smolagents.models import ChatMessage
import platform
import shutil

STRICT_INSTRUCTIONS = """You are a DevOps automation assistant that executes tasks step-by-step using tools.

PROCESS:
1. Think through the problem and available tools
2. Create a step-by-step plan
3. Execute tool calls in sequence, validating each step
4. Use actual values from tool responses in subsequent calls

CRITICAL RULES:
1. IMPORTANT: Output EXACTLY ONE <tool_call> per response - nothing more
2. After you call a tool, STOP and WAIT for the response before calling the next tool
3. Use ONLY <tool_call> XML tags for tool calls (must wrap each call in <tool_call>...</tool_call>)
4. NEVER call final_answer together with other tools - it must be alone in its own response
5. When you receive tool responses, use the ACTUAL values in your next tool calls
6. If you encounter an error, try a DIFFERENT approach (not same failing call twice)
7. VALIDATION: After EVERY tool call (except final_answer), verify it succeeded:
   - For bash: Check output for error keywords (Error, error, failed, Failed, not found, No such file)
   - For write_file: Use bash "ls -la <path>" to confirm file exists
   - For read_file: Verify content was returned (not empty or error)
   - If step failed, try alternative approach or debug with verification commands
   - Example: After "brew install X", verify with "which X" or "brew list | grep X"

TOOL CALL FORMAT (must use XML tags):
<tool_call>
{"name": "tool_name", "arguments": {"arg1": "value1", "arg2": "value2"}}
</tool_call>

PLANNING EXAMPLE:
Task: Get DOCKER_USER environment variable and create a Dockerfile using it

STEP 1: Think and plan
<think>
I need to:
1. Get the DOCKER_USER environment variable
2. Create a Dockerfile that uses this user
3. Return the result
</think>

<plan>
1. Get DOCKER_USER environment variable using get_env
2. Write a Dockerfile with the user value to a file
3. Provide final answer with the completed task
</plan>

STEP 2: Call FIRST tool ONLY (output one tool per response):
<tool_call>
{"name": "get_env", "arguments": {"key": "DOCKER_USER"}}
</tool_call>

STEP 3: After receiving response (e.g., "The value is: john"), call NEXT tool:
<tool_call>
{"name": "write_file", "arguments": {"path": "Dockerfile", "content": "FROM alpine\\nRUN useradd -m john"}}
</tool_call>

STEP 4: After verification response, finalize:
<tool_call>
{"name": "final_answer", "arguments": {"answer": "Dockerfile created with user john from environment"}}
</tool_call>

KEY: Each response contains EXACTLY ONE <tool_call> block. The agent loop handles sequential execution.

KEY POINTS:
- Always plan before executing tools
- One tool call at a time
- Use actual values from responses, not placeholders
- Validate each step before moving to next
- If something fails, debug with additional bash commands instead of repeating identical calls
"""


# STRICT_INSTRUCTIONS = """You are a DevOps automation assistant.

#   When given a task:

#   1. Think through the problem
#   2. Provide a step-by-step plan
#   3. Execute tool calls to complete the plan

#   REASONING:
#   <think>
#   Analyze what needs to be done, what tools are available, and the sequence of steps.
#   </think>

#   PLAN:
#   <plan>
#   1. Step one (what it does)
#   2. Step two (what it does)
#   3. Step three (what it does)
#   </plan>

#   TOOL CALLS:
#   Execute calls in sequence. Each tool call is:
#   <tool>
#   {"name": "tool_name", "arguments": {"arg": "value"}}
#   </tool>

#   AVAILABLE TOOLS:
#   - read_file: {"name": "read_file", "arguments": {"path": "file_path"}}
#   - write_file: {"name": "write_file", "arguments": {"path": "file_path", "content": "content"}}
#   - bash: {"name": "bash", "arguments": {"command": "shell_command"}}
#   - get_env: {"name": "get_env", "arguments": {"key": "ENV_VAR_NAME"}}
#   - final_answer: {"name": "final_answer", "arguments": {"answer": "result"}}

#   EXAMPLE:
#   Task: Get DOCKER_USER and echo it

#   <think>
#   Need to read the environment variable DOCKER_USER, then output it.
#   </think>

#   <plan>
#   1. Get DOCKER_USER environment variable
#   2. Return the value as the final answer
#   </plan>

#   {"name": "get_env", "arguments": {"key": "DOCKER_USER"}}
#   {"name": "final_answer", "arguments": {"answer": "Retrieved DOCKER_USER value"}}

# """

class OllamaChat:
    """
    SmolAgents-compatible Ollama backend.
    Simplifies system prompt, flattens messages, and supports simple tool call parsing.
    """

    def __init__(self, model="qwen3:1.7b", #"hf.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF:Q6_K"
                 endpoint="http://localhost:11434/api/chat"):
        self.model = model
        self.endpoint = endpoint
        self.name = "OllamaChat"
        self.supports_streaming = False

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    def _serialize_messages(self, messages):
        """Flatten SmolAgents ChatMessages into Ollama-compatible format."""
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

            # Convert role to string and normalize for QWEN
            role_str = str(role).split(".")[-1].lower()  # MessageRole.TOOL_RESPONSE → "tool_response"

            # Map SmolAgents roles to QWEN's expected roles
            if role_str == "tool_response":
                role_str = "tool"  # QWEN expects "tool" for tool responses

            serialized.append({"role": role_str, "content": content})
        return serialized



    def _build_tool_list(self, tools):
        """Build minimal tool list - model was trained on these tools."""
        lines = ["Available tools:"]
        tool_objs = tools.values() if isinstance(tools, dict) else tools
        for t in tool_objs:
            name = getattr(t, "name", getattr(t, "__name__", "unknown"))
            desc = (getattr(t, "description", None) or getattr(t, "__doc__", "") or "").strip()
            if desc:
                lines.append(f"- {name}: {desc}")
            else:
                lines.append(f"- {name}")

        return "\n".join(lines)
    # -------------------------------------------------------------------------
    # Core API
    # -------------------------------------------------------------------------


    def generate(self, messages, tools=None, stop_sequences=None, **kwargs):
        """
        Generate a single assistant message.
        This trims the system prompt and adds a compact tool schema that Ollama can understand.
        """
        
        tools = tools or kwargs.get("tools") or getattr(self, "tools", [])

        # 1️⃣ Convert messages into mutable list
        flattened_msgs = self._serialize_messages(messages)

        # 2️⃣ Patch the system prompt
        for msg in flattened_msgs:
            role_str = str(msg.get("role", "")).split(".")[-1].lower()
            msg["role"] = role_str  # Normalize!

            if role_str == "system":
                msg["content"] = (
                    STRICT_INSTRUCTIONS.strip()
                    + "\n\nSystem information:\n"
                    + self._build_tool_list(tools or [])
                )


        # 3️⃣ POST to Ollama
        payload = {
            "model": self.model,
            "messages": flattened_msgs,
            "stream": False,
        }

        # Debug: print what is sent (only if DEBUG env var is set)
        if os.getenv('DEBUG_OLLAMA') == '1':
            print("\n=== PAYLOAD SENT TO OLLAMA (trimmed) ===")
            print(json.dumps(payload, indent=2) + "...\n")

        resp = requests.post(self.endpoint, json=payload, timeout=300)
        if not resp.ok:
            raise RuntimeError(f"Ollama returned {resp.status_code}: {resp.text}")

        data = resp.json()

        if os.getenv('DEBUG_OLLAMA') == '1':
            print("\n🟩 === [RECV] Ollama Response ===")
            print(json.dumps(data, indent=2, ensure_ascii=False))

        # 4️⃣ Extract assistant content
        content = ""
        if "message" in data:
            content = data["message"].get("content", "").strip()
        elif "response" in data:
            content = data["response"].strip()
        else:
            content = str(data)

        # 5️⃣ Return a proper ChatMessage (SmolAgents expects this type)
        return ChatMessage(role="assistant", content=content)

    # -------------------------------------------------------------------------
    # Tool call parsing
    # -------------------------------------------------------------------------

    def parse_tool_calls(self, message):
        """
        Parse model output in QWEN's native XML format:
        <tool_call>
        {"name": "tool_name", "arguments": {"arg": "value"}}
        </tool_call>
        Return SmolAgents-compatible ChatToolCall list.
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

        # Try parsing XML <tool_call> tags first (QWEN's official format)
        # Extract everything between <tool_call> and </tool_call>, then parse as JSON
        # Use greedy match (.*) instead of non-greedy (.*?) to capture full JSON with nested braces
        xml_matches = list(re.finditer(r"<tool_call>\s*(.*)\s*</tool_call>", text, re.DOTALL))

        # ENFORCE: Exactly ONE tool call per response
        if len(xml_matches) > 1:
            error_msg = f"ERROR: You called {len(xml_matches)} tools in one response. You MUST call EXACTLY ONE tool per response. Please output only ONE <tool_call> block and try again."
            print(f"\n❌ {error_msg}\n")

            # Raise exception so it gets caught as an error by the agent
            raise ValueError(error_msg)

        # Process the single tool call (or none)
        for match in xml_matches:
            try:
                # Strip whitespace from captured JSON to handle trailing newlines
                json_str = match.group(1).strip()

                # AUTO-FIX: Add missing closing brace if needed
                # Model sometimes generates incomplete JSON missing the final }
                open_braces = json_str.count('{')
                close_braces = json_str.count('}')
                if open_braces > close_braces:
                    missing = open_braces - close_braces
                    json_str += '}' * missing
                    if os.getenv('DEBUG_OLLAMA') == '1':
                        print(f"🔧 Auto-fixed JSON by adding {missing} closing brace(s)")

                tool_data = json.loads(json_str)
                name = tool_data.get("name", "unknown")
                args = tool_data.get("arguments", {})

                func = FunctionCall(name=name, arguments=args)

                try:
                    call = ChatToolCall(id=str(uuid.uuid4()), function=func)
                except TypeError:
                    call = ChatToolCall(function=func)

                calls.append(call)
            except json.JSONDecodeError as e:
                print(f"❌ ERROR: Failed to parse tool call JSON even after auto-fix attempt: {e}")
                print(f"📄 Original JSON was: {match.group(1).strip()}")
                print(f"📄 After auto-fix: {json_str}")
                continue

        # If no XML tags found, try markdown JSON blocks (QWEN small models often use this)
        if not calls:
            for match in re.finditer(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL):
                try:
                    tool_data = json.loads(match.group(1))
                    # Check if it looks like a tool call (has "name" and "arguments")
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
        # This prevents the agent from getting stuck in an infinite loop
        has_final_answer = any(call.function.name == "final_answer" for call in calls)
        has_other_tools = any(call.function.name != "final_answer" for call in calls)

        if has_final_answer and has_other_tools:
            print("\n⚠️  WARNING: Model tried to call final_answer with other tools. Stripping final_answer to prevent loop.")
            calls = [c for c in calls if c.function.name != "final_answer"]

        if hasattr(message, "__dict__"):
            message.tool_calls = calls
        return message
