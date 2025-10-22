from smolagents import CodeAgent, tool, ToolCallingAgent
from ollama_backend import OllamaChat
import os
import subprocess

# ─────────────────────────────────────────────
# 1️⃣ Monkey-patch SmolAgents' default system message
# ─────────────────────────────────────────────
def _minimal_system_message(self):
    return ""  # Disable SmolAgents’ long default prompt entirely

ToolCallingAgent._make_system_message = _minimal_system_message

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
def run_command(command: str) -> str:
    """
    Execute a shell command and return its output.

    Args:
        command (str): The shell command to execute.

    Returns:
        str: The output or error text from the command.
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
    tools=[read_file, write_file, run_command, get_env],
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
