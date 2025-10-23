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

# Model backend
model = OllamaChat(model="qwen3:1.7b")



class DevOpsAgent(ToolCallingAgent):
    def _run_model(self, messages, stop_sequences=None):
        # Always forward self.tools to the model
        return self.model.generate(messages, tools=self.tools, stop_sequences=stop_sequences)


agent = DevOpsAgent(
    tools=[read_file, write_file, bash, get_env],
    model=model,
    instructions="You are a DevOps automation assistant; use the tools provided and call no other code.",
    max_steps=4  # Prevent infinite loops - stop after 10 steps
)



model.tools = agent.tools

# CLI argument support
if __name__ == "__main__":
    import sys

    # Check if query provided as argument
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        # Default query if none provided
        query = "Read AWS credentials from the environment and create a Dockerfile that prints $DOCKER_USER"
        print(f"ℹ️  No query provided. Using default query.")
        print(f"   Usage: python agent.py \"<your query here>\"\n")

    result = agent.run(query)
    print("\n=== FINAL RESULT ===")
    print(result)
