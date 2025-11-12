# llamacpp_backend.py
import json, re, uuid, os
from smolagents.models import ChatMessage
from llama_cpp import Llama

# Import the same system prompt from ollama_backend
from ollama_backend import STRICT_INSTRUCTIONS

class LlamaCppChat:
    """
    SmolAgents-compatible llama-cpp-python backend.
    Provides automatic prompt caching for faster repeated queries.
    """

    def __init__(self, model_path="./qwen-devops-442-q4_k_m.gguf", n_ctx=8192, n_threads=None):
        self.model_path = model_path
        self.name = "LlamaCppChat"
        self.supports_streaming = False

        # Auto-detect threads (use all cores)
        if n_threads is None:
            import multiprocessing
            n_threads = multiprocessing.cpu_count()

        print(f"Loading model from {model_path} with {n_threads} threads...")
        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            verbose=False
        )
        print("Model loaded!")

    def _serialize_messages(self, messages):
        """Flatten SmolAgents ChatMessages into llama.cpp-compatible format."""
        serialized = []
        for m in messages:
            # Determine role
            role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else "user")

            # Extract content
            raw_content = getattr(m, "content", None) or (
                m.get("content") if isinstance(m, dict) else str(m)
            )

            # Flatten [{type:text, text:...}] → "..."
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
            role_str = str(role).split(".")[-1].lower()

            # Map SmolAgents roles to standard chat roles
            if role_str == "tool_response":
                role_str = "user"  # llama.cpp expects user/assistant/system

            serialized.append({"role": role_str, "content": content})
        return serialized

    def _build_tool_list(self, tools):
        """Build minimal tool list for system prompt."""
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

    def generate(self, messages, tools=None, stop_sequences=None, **kwargs):
        """
        Generate a single assistant message.
        Prompt caching is automatic - llama.cpp reuses KV cache for matching prefixes.
        """

        tools = tools or kwargs.get("tools") or getattr(self, "tools", [])

        # Convert messages
        flattened_msgs = self._serialize_messages(messages)

        # Patch the system prompt
        for msg in flattened_msgs:
            if msg["role"] == "system":
                msg["content"] = (
                    STRICT_INSTRUCTIONS.strip()
                    + "\n\nSystem information:\n"
                    + self._build_tool_list(tools or [])
                )

        # Debug output
        if os.getenv('DEBUG_LLAMACPP') == '1':
            print("\n=== MESSAGES SENT TO LLAMA.CPP ===")
            print(json.dumps(flattened_msgs, indent=2))

        # Call llama.cpp (automatic KV caching!)
        response = self.llm.create_chat_completion(
            messages=flattened_msgs,
            max_tokens=2048,  # Increased from 512 to allow full tool call generation
            temperature=0.7,
            top_p=0.95,  # Slightly increased for more diverse outputs
            repeat_penalty=1.1,  # Discourage repetition
            stop=stop_sequences or []
        )

        if os.getenv('DEBUG_LLAMACPP') == '1':
            print("\n=== LLAMA.CPP RESPONSE ===")
            print(json.dumps(response, indent=2, ensure_ascii=False))

        # Extract content
        content = response["choices"][0]["message"]["content"].strip()

        # Return ChatMessage
        return ChatMessage(role="assistant", content=content)

    def parse_tool_calls(self, message):
        """
        Parse model output in QWEN's native XML format.
        Returns SmolAgents-compatible ChatToolCall list.
        """
        # Import tool call classes
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

        # Parse XML <tool_call> tags
        xml_matches = list(re.finditer(r"<tool_call>\s*(.*)\s*</tool_call>", text, re.DOTALL))

        # Enforce one tool call per response
        if len(xml_matches) > 1:
            error_msg = f"ERROR: You called {len(xml_matches)} tools in one response. You MUST call EXACTLY ONE tool per response."
            print(f"\n❌ {error_msg}\n")
            raise ValueError(error_msg)

        for match in xml_matches:
            try:
                tool_data = json.loads(match.group(1).strip())
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
                print(f"📄 Malformed JSON was: {match.group(1)}")
                continue

        # Try markdown JSON blocks if no XML found
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

        # Safety: strip final_answer if mixed with other tools
        has_final_answer = any(call.function.name == "final_answer" for call in calls)
        has_other_tools = any(call.function.name != "final_answer" for call in calls)

        if has_final_answer and has_other_tools:
            print("\n⚠️  WARNING: Model tried to call final_answer with other tools. Stripping final_answer.")
            calls = [c for c in calls if c.function.name != "final_answer"]

        if hasattr(message, "__dict__"):
            message.tool_calls = calls
        return message
