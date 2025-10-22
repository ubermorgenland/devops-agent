# ollama_backend.py
import json, re, uuid, os
import requests
from smolagents.models import ChatMessage
import platform
import shutil

STRICT_INSTRUCTIONS = """
You are a DevOps automation agent that executes tasks step-by-step using tools.

CRITICAL RULES:
1. Respond with tool calls in this format: Tool:<tool_name>({"arg1": "value1"})
2. You may call multiple tools together, EXCEPT final_answer
3. NEVER combine final_answer with any other tool call
4. When the task is complete, your ENTIRE response must be ONLY:
   Tool:final_answer({"answer": "<your final answer>"})
5. Never include natural language, explanations, or markdown
6. If you encounter an error, try a different approach
7. Do NOT repeat the same failing tool call twice with identical arguments

EXAMPLES:
Good (multiple tools):
Tool:get_env({"key": "DOCKER_USER"})
Tool:write_file({"path": "Dockerfile", "content": "FROM alpine"})

Good (final answer alone):
Tool:final_answer({"answer": "Task completed"})

BAD (never do this):
Tool:run_command({"command": "ls"})
Tool:final_answer({"answer": "Done"})
"""


class OllamaChat:
    """
    SmolAgents-compatible Ollama backend.
    Simplifies system prompt, flattens messages, and supports simple tool call parsing.
    """

    def __init__(self, model="hf.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF:Q6_K",
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

            serialized.append({"role": str(role), "content": content})
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

        # 3️⃣ Tool usage examples
        examples = [
            "",
            "Example tool calls:",
            'Tool:get_env({"key": "DOCKER_USER"})',
            'Tool:write_file({"path": "Dockerfile", "content": "FROM alpine\\nCMD echo $DOCKER_USER"})',
            'Tool:run_command({"command": "echo $DOCKER_USER"})',
            "",
            "When you are done, finalize with:",
            'Tool:final_answer({"answer": "..."})',
        ]

        return "\n".join([system_section] + lines + examples)
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

        # Debug: print what is sent
        print("\n=== PAYLOAD SENT TO OLLAMA (trimmed) ===")
        print(json.dumps(payload, indent=2) + "...\n")

        resp = requests.post(self.endpoint, json=payload, timeout=300)
        if not resp.ok:
            raise RuntimeError(f"Ollama returned {resp.status_code}: {resp.text}")

        data = resp.json()

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
        Parse model output like:
        Tool:get_env({"key": "DOCKER_USER"})
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

        for match in re.finditer(r"Tool:([a-zA-Z0-9_]+)\((\{.*?\})\)", text):
            name = match.group(1)
            try:
                args = json.loads(match.group(2))
            except json.JSONDecodeError:
                args = {"raw": match.group(2)}

            func = FunctionCall(name=name, arguments=args)

            # ✅ Ensure every call has a unique id
            try:
                call = ChatToolCall(id=str(uuid.uuid4()), function=func)
            except TypeError:
                # fallback for older versions that don't take id
                call = ChatToolCall(function=func)

            calls.append(call)

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
