from smolagents import CodeAgent, tool, ToolCallingAgent
from smolagents.models import ChatMessage, MessageRole
from ollama_backend import OllamaChat
import os
import subprocess
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

# Apply SmolAgents monkey patches for clean real-time output
import smolagents_patches

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
ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
ollama_endpoint = f"{ollama_host}/api/chat" if not ollama_host.endswith("/api/chat") else ollama_host
model = OllamaChat(model="qwen3-devops", endpoint=ollama_endpoint)



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
        # Enable/disable tool approval prompts
        self.require_approval = os.getenv('REQUIRE_APPROVAL') == '1'

    def ask_user_approval(self, tool_name: str, arguments: dict):
        """
        Ask user for approval before executing a tool.
        Returns (approved: bool, comment: str)
        """
        import json

        # Format arguments nicely
        args_str = json.dumps(arguments, indent=2)

        print(f"\n🔧 Tool call requested:")
        print(f"   Tool: {tool_name}")
        print(f"   Arguments: {args_str}")
        print()

        # Ask for approval
        while True:
            response = input("Approve this tool call? [y/n]: ").strip().lower()

            if response in ['y', 'yes']:
                return True, ""
            elif response in ['n', 'no']:
                # Ask for optional comment
                comment = input("Optional feedback for the agent (press Enter to skip): ").strip()
                return False, comment
            else:
                print("Please answer 'y' or 'n'")
                continue

    def _run_model(self, messages, stop_sequences=None):
        # Always forward self.tools to the model
        result = self.model.generate(messages, tools=self.tools, stop_sequences=stop_sequences)
        return result

    def execute_tool_call(self, tool_name: str, arguments: dict):
        """
        Override tool execution to prevent hallucinated final_answer calls.
        Check if final_answer is called without any prior tool executions.
        Also detect if the model is repeating the same tool call.
        Optionally ask for user approval before executing tools.
        """
        # Ask for user approval if enabled (skip for final_answer)
        if self.require_approval and tool_name != "final_answer":
            approved, comment = self.ask_user_approval(tool_name, arguments)

            if not approved:
                # User rejected - create a rejection message for the LLM
                rejection_message = "User rejected this tool call."
                if comment:
                    rejection_message += f" User comment: {comment}"

                # Instead of raising an error, we'll temporarily replace the tool
                # with one that just returns the rejection message
                # This keeps the agent in its thinking loop
                original_tool = None
                tool_obj = None

                # Find the tool in self.tools
                if isinstance(self.tools, dict):
                    tool_obj = self.tools.get(tool_name)
                else:
                    for t in self.tools:
                        if getattr(t, 'name', getattr(t, '__name__', None)) == tool_name:
                            tool_obj = t
                            break

                if tool_obj:
                    # Save original forward function
                    original_forward = getattr(tool_obj, 'forward', None)

                    # Create a lambda that returns rejection message
                    def rejection_func(*args, **kwargs):
                        return rejection_message

                    # Temporarily replace the tool's forward method
                    tool_obj.forward = rejection_func

                    try:
                        # Execute with the fake tool
                        result = super().execute_tool_call(tool_name, arguments)
                    finally:
                        # Restore original function
                        if original_forward:
                            tool_obj.forward = original_forward

                    return result
                else:
                    # If we can't find the tool, raise error as fallback
                    raise ValueError(rejection_message)

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


# CLI argument support
if __name__ == "__main__":
    import sys

    # Check for verbose, interactive, and approval flags
    verbose = '--verbose' in sys.argv or '-v' in sys.argv or os.getenv('VERBOSE') == '1'
    interactive = '--interactive' in sys.argv or '-i' in sys.argv
    require_approval = '--require-approval' in sys.argv or '-a' in sys.argv or os.getenv('REQUIRE_APPROVAL') == '1'
    args = [arg for arg in sys.argv[1:] if arg not in ('--verbose', '-v', '--interactive', '-i', '--require-approval', '-a')]

    # Set debug mode
    if not verbose:
        os.environ['DEBUG_OLLAMA'] = '0'
        os.environ['SMOLAGENTS_LOG_LEVEL'] = 'WARNING'  # Suppress debug output

    # Set approval mode
    if require_approval:
        os.environ['REQUIRE_APPROVAL'] = '1'

    # Create agent AFTER setting environment variables
    agent = DevOpsAgent(
        tools=[read_file, write_file, bash, get_env],
        model=model,
        instructions="You are a DevOps automation assistant; use the tools provided and call no other code.",
        max_steps=15  # Allow more steps for error recovery and debugging
    )
    model.tools = agent.tools

    # Interactive mode
    if interactive or len(args) == 0:
        # Set up prompt_toolkit for command history and arrow key support
        history_file = os.path.expanduser("~/.devops_agent_history")

        # Create a prompt session with history
        session = PromptSession(history=FileHistory(history_file))

        print("🤖 DevOps Agent - Interactive Mode")
        if require_approval:
            print("⚠️  Approval mode enabled - you'll be asked to approve each tool call")
        print("Type your task and press Enter. Type 'exit' or 'quit' to leave.\n")

        while True:
            try:
                # Prompt for input with arrow key support and history
                query = session.prompt("\n> ").strip()

                # Check for exit commands
                if query.lower() in ['exit', 'quit', 'q']:
                    print("\nGoodbye!")
                    break

                # Skip empty input
                if not query:
                    continue

                # Check for help command
                if query.lower() in ['help', '?']:
                    print("\nAvailable commands:")
                    print("  - Type any DevOps task (e.g., 'Get all pods')")
                    print("  - 'exit' or 'quit' - Exit interactive mode")
                    print("  - 'help' - Show this message")
                    continue

                # Reset agent state for clean execution
                agent.last_tool_call = None

                # Execute the task - real-time filtering handled by smolagents_patches
                print()  # Blank line before output
                result = agent.run(query)
                print(f"\n✅ {result}")

            except KeyboardInterrupt:
                print("\n\nInterrupted. Type 'exit' to quit.")
                continue
            except Exception as e:
                error_msg = str(e)
                # Filter out internal error messages meant for the agent, not the user
                # But keep user rejection messages (those are real user feedback)
                if "REPETITION DETECTED" in error_msg or "HALLUCINATION ALERT" in error_msg:
                    # These are feedback for the LLM - don't show to user
                    # Agent will have already tried to self-correct through SmolAgents' error handling
                    continue
                else:
                    # Show actual errors (command failures, file not found, user rejections, etc.)
                    print(f"\n❌ Error: {e}")
                continue

        sys.exit(0)

    # Single command mode
    query = " ".join(args)

    print(f"📋 Task: {query}\n")

    # Real-time filtering handled by smolagents_patches
    result = agent.run(query)
    print(f"\n✅ Result:\n{result}\n")
