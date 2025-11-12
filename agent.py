from smolagents import CodeAgent, tool, ToolCallingAgent
from smolagents.models import ChatMessage, MessageRole
from ollama_backend import OllamaChat
import os
import subprocess

# ─────────────────────────────────────────────
# 1️⃣ Monkey-patch SmolAgents' default system message
# ─────────────────────────────────────────────
def _minimal_system_message(self):
    return ""  # Disable SmolAgents' long default prompt entirely

ToolCallingAgent._make_system_message = _minimal_system_message

# ─────────────────────────────────────────────
# 2️⃣ Monkey-patch ActionStep.to_messages() for QWEN-friendly tool response formatting
# ─────────────────────────────────────────────
from smolagents.memory import ActionStep

# Store original method
_original_to_messages = ActionStep.to_messages

def _qwen_friendly_to_messages(self, summary_mode=False):
    """
    Override tool response formatting to be more explicit for small models.
    Instead of generic 'Observation: value', format as:
    'Tool <tool_name> returned: <value>. Use this value in your next steps.'
    """
    messages = []

    # Add model output message (assistant's tool call response)
    if self.model_output_message:
        messages.append(self.model_output_message)
    elif self.model_output:
        # Handle cases where model_output is a string
        content = self.model_output if isinstance(self.model_output, str) else str(self.model_output)
        messages.append(
            ChatMessage(
                role=MessageRole.ASSISTANT,
                content=content.strip(),
            )
        )

    # Add tool response with explicit formatting for QWEN
    if self.observations is not None:
        # Parse which tool was called to make response more explicit
        tool_name = "unknown_tool"
        if self.tool_calls and len(self.tool_calls) > 0:
            # ToolCall has 'name' directly, not 'function.name'
            tool_name = self.tool_calls[0].name

        # Format observation to be explicit about value usage
        observation_text = self.observations.strip()

        # Handle empty responses explicitly to prevent hallucination
        # BUT: Skip this for final_answer, which is supposed to return nothing
        if tool_name != "final_answer" and (not observation_text or observation_text == ""):
            formatted_observation = "Command executed successfully but returned no output. This likely means no results were found or nothing is configured. Try an alternative command or report this accurately."
        else:
            # Simpler, clearer format for small models
            formatted_observation = f"The value is: {observation_text}"

        messages.append(
            ChatMessage(
                role=MessageRole.TOOL_RESPONSE,
                content=[
                    {
                        "type": "text",
                        "text": formatted_observation,
                    }
                ],
            )
        )

    # Add error message if present
    if self.error is not None:
        error_message = (
            "Error:\n"
            + str(self.error)
            + "\nNow let's retry: take care not to repeat previous errors!"
        )
        message_content = f"Call id: {self.tool_calls[0].id}\n" if self.tool_calls else ""
        message_content += error_message
        messages.append(
            ChatMessage(role=MessageRole.TOOL_RESPONSE, content=[{"type": "text", "text": message_content}])
        )

    return messages

# Apply the patch
ActionStep.to_messages = _qwen_friendly_to_messages

# ─────────────────────────────────────────────
# 3️⃣ Monkey-patch SmolAgents logger for compact tool call display
# ─────────────────────────────────────────────
from smolagents import AgentLogger
from rich.panel import Panel
from rich.text import Text
import re

_original_log = AgentLogger.log

def _compact_log(self, message, level=None, **kwargs):
    """Reformat tool call messages to be more compact"""
    if isinstance(message, Panel) and hasattr(message, 'renderable'):
        text_str = str(message.renderable)

        # Format: "Calling tool: 'bash' with arguments: {'command': 'X'}" -> "bash {X}"
        # Use DOTALL to match across newlines for long argument values
        match = re.search(r"Calling tool: '(\w+)' with arguments: \{[^:]+: '(.+?)'\}", text_str, re.DOTALL)
        if match:
            tool_name = match.group(1)
            arg_value = match.group(2)
            # For final_answer, just show the answer
            if tool_name == "final_answer":
                message = Panel(Text(arg_value))
            else:
                message = Panel(Text(f"{tool_name} {{{arg_value}}}"))
        else:
            # Try with double quotes (for arguments with quotes or special chars)
            match = re.search(r'Calling tool: \'(\w+)\' with arguments: \{[^:]+: "(.+?)"\}', text_str, re.DOTALL)
            if match:
                tool_name = match.group(1)
                arg_value = match.group(2)
                # For final_answer, just show the answer
                if tool_name == "final_answer":
                    message = Panel(Text(arg_value))
                else:
                    message = Panel(Text(f"{tool_name} {{{arg_value}}}"))

    return _original_log(self, message, level, **kwargs)

AgentLogger.log = _compact_log

# Define tools using decorator
@tool
def read_file(path: str) -> str:
    """
    Read the content of a file at the given path.

    Args:
        path (str): The path to the file to read.

    Returns:
        str: The file content.
    """
    with open(path, "r") as f:
        return f.read()

@tool
def write_file(path: str, content: str) -> str:
    """
    Write content to a file.

    Args:
        path (str): Path to the file to write.
        content (str): The content to write to the file.

    Returns:
        str: Confirmation message.
    """
    with open(path, "w") as f:
        f.write(content)
    return f"Wrote {len(content)} bytes to {path}"

@tool
def bash(command: str) -> str:
    """
    Execute a bash command and return its output. Use this for shell operations like 'ls', 'echo', 'grep', etc.

    Args:
        command (str): The bash command to execute (e.g., "ls *.txt", "echo Hello World").

    Returns:
        str: The command output. Always include this output in your final answer when the user asks about command results.
    """

    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout or result.stderr

@tool
def get_env(key: str) -> str:
    """
    Get the value of an environment variable.

    Args:
        key (str): Name of the environment variable.

    Returns:
        str: The variable value or an error message if not set.
    """
    value = os.getenv(key)
    if value is None:
        return f"ERROR: Environment variable '{key}' is not set"
    return value

# Model backend - using merged model (LoRA weights merged into base model for faster inference)
model = OllamaChat(model="qwen-devops-v2") #devops-merged (LoRA merged) vs devops-sft (LoRA separate)



class DevOpsAgent(ToolCallingAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.verbose = os.getenv('VERBOSE') == '1'
        self.thinking_words = [
            "thinking", "pondering", "analyzing", "processing", "evaluating",
            "computing", "deliberating", "reasoning", "calculating", "inferring",
            "discombulating", "cogitating", "ruminating"
        ]
        # Track last tool call to detect repetition
        self.last_tool_call = None

    def _run_model(self, messages, stop_sequences=None):
        # Always forward self.tools to the model
        result = self.model.generate(messages, tools=self.tools, stop_sequences=stop_sequences)
        return result

    def execute_tool_call(self, tool_name: str, arguments: dict):
        """
        Override tool execution to prevent hallucinated final_answer calls.
        Check if final_answer is called without any prior tool executions.
        Also detect if the model is repeating the same tool call.
        """
        # Create a signature for this tool call (tool name + arguments)
        import json
        current_call_signature = json.dumps({"tool": tool_name, "args": arguments}, sort_keys=True)

        # Check for repetition (calling the same tool with same parameters twice in a row)
        if self.last_tool_call == current_call_signature and tool_name != "final_answer":
            raise ValueError(
                f"REPETITION DETECTED: You just called '{tool_name}' with the exact same parameters. "
                f"You already received the result from this command. Do not repeat the same tool call! "
                f"If you have the data you need, call final_answer with your conclusion. "
                f"If you need different data, call a different tool or use different parameters."
            )

        # Update last tool call (but not for final_answer, as it doesn't produce data)
        if tool_name != "final_answer":
            self.last_tool_call = current_call_signature

        # Check if this is a final_answer call without prior tool executions
        if tool_name == "final_answer":
            # Count how many actual tool calls (non-final_answer) have been executed
            actual_tool_calls = 0
            if hasattr(self, 'memory') and self.memory:
                # Access steps from AgentMemory
                steps = getattr(self.memory, 'steps', [])
                for step in steps:
                    if hasattr(step, 'tool_calls') and step.tool_calls:
                        for tool_call in step.tool_calls:
                            # Get tool name from the tool call
                            if hasattr(tool_call, 'name'):
                                call_name = tool_call.name
                            elif hasattr(tool_call, 'function') and hasattr(tool_call.function, 'name'):
                                call_name = tool_call.function.name
                            else:
                                continue

                            # Count non-final_answer tools
                            if call_name != "final_answer":
                                actual_tool_calls += 1

            # If no actual tools were called, reject the final_answer
            if actual_tool_calls == 0:
                raise ValueError(
                    "HALLUCINATION ALERT: You called final_answer without executing any tools! "
                    "You must actually run commands (bash, read_file, write_file, get_env) before providing a final answer. "
                    "Please execute the appropriate tools first to gather real data, then call final_answer with the actual results."
                )

        # Call the parent's execute_tool_call method
        return super().execute_tool_call(tool_name, arguments)


agent = DevOpsAgent(
    tools=[read_file, write_file, bash, get_env],
    model=model,
    instructions="You are a DevOps automation assistant; use the tools provided and call no other code.",
    max_steps=15  # Allow more steps for error recovery and debugging
)



model.tools = agent.tools

# CLI argument support
if __name__ == "__main__":
    import sys

    # Check for verbose flag
    verbose = '--verbose' in sys.argv or '-v' in sys.argv or os.getenv('VERBOSE') == '1'
    args = [arg for arg in sys.argv[1:] if arg not in ('--verbose', '-v')]

    # Set debug mode
    if not verbose:
        os.environ['DEBUG_OLLAMA'] = '0'
        os.environ['SMOLAGENTS_LOG_LEVEL'] = 'WARNING'  # Suppress debug output

    # Check if query provided as argument
    if len(args) > 0:
        query = " ".join(args)
    else:
        # Default query if none provided
        query = "Get all pods in default namespace"
        print(f"ℹ️  No query provided. Using default query.")
        print(f"   Usage: python agent.py \"<your query here>\" [--verbose]\n")

    print(f"📋 Task: {query}\n")

    # Filter out Step headers if not verbose
    if not verbose:
        import io, sys, re
        from contextlib import redirect_stdout

        # Capture stdout only (stderr shows thinking indicators)
        captured = io.StringIO()
        with redirect_stdout(captured):
            result = agent.run(query)

        # Filter and print
        output = captured.getvalue()
        lines = output.split('\n')
        in_model_output = False

        for i, line in enumerate(lines):
            # Track when we're inside model output sections
            if 'Output message of the LLM:' in line:
                in_model_output = True
                continue
            if line.strip().startswith('╭') and in_model_output:
                in_model_output = False

            # Skip model output, debug lines, and XML tags
            stripped = line.strip()
            if (in_model_output or
                re.match(r'^.*Step \d+.*$', line) or
                re.match(r'^\[Step \d+:.*\]$', line) or
                re.match(r'^[12]$', line) or
                re.match(r'^\s*"(name|arguments|command|answer|id|function)":', line) or  # JSON keys with whitespace
                re.match(r'^\s*[{}]\s*$', line) or  # Standalone braces
                '"name":' in stripped or
                '"arguments":' in stripped or
                '"command":' in stripped or
                '"answer":' in stripped):
                continue

            # Skip "Final answer:" lines (they duplicate the result at the end)
            if 'Final answer:' in line:
                continue

            # Remove trailing " 1" from lines FIRST (before duplicate checking)
            line = re.sub(r'\s+1$', '', line)

            # Skip if this line is a duplicate of the result (final answer observations)
            if line.strip() and len(line.strip()) > 20 and line.strip() in str(result):
                continue

            # Fix "Observations:" formatting - add newline after it if there's text on the same line
            if line.startswith('Observations: ') and len(line) > 14:
                # There's text after "Observations: " - split it
                print('Observations:')
                print(line[14:])  # Print the rest on next line
                continue

            # Skip standalone "Observations:" if it's near the end (likely final answer)
            if line.strip() == 'Observations:':
                remaining = len(lines) - i
                if remaining < 5:  # Near the end, likely final answer
                    continue

            print(line)

        print(f"\n✅ Result:\n{result}\n")
    else:
        result = agent.run(query)
        print(f"\n✅ Result:\n{result}\n")
