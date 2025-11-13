"""
Monkey patches for SmolAgents to enable clean, real-time output filtering.
"""
import os
import re
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from smolagents import ToolCallingAgent
from smolagents.memory import ActionStep
from smolagents.models import ChatMessage, MessageRole


# ─────────────────────────────────────────────
# 1️⃣ Disable SmolAgents' default system message
# ─────────────────────────────────────────────
def _minimal_system_message(self):
    return ""  # Disable SmolAgents' long default prompt entirely

ToolCallingAgent._make_system_message = _minimal_system_message


# ─────────────────────────────────────────────
# 2️⃣ QWEN-friendly tool response formatting
# ─────────────────────────────────────────────
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

ActionStep.to_messages = _qwen_friendly_to_messages


# ─────────────────────────────────────────────
# 3️⃣ Real-time output filtering via Rich Console
# ─────────────────────────────────────────────
from rich.rule import Rule

_original_print = Console.print

def _filtered_print(self, *args, **kwargs):
    """Filter SmolAgents output in real-time"""
    # Skip filtering if verbose mode
    if os.getenv('VERBOSE') == '1':
        return _original_print(self, *args, **kwargs)

    # Check if this is something we want to filter out
    if args:
        first_arg = args[0]

        # Filter out Rich Rule objects (step separators like ━━━━━━)
        if isinstance(first_arg, Rule):
            # Check if it's a step separator
            rule_text = str(first_arg.title) if hasattr(first_arg, 'title') else ""
            if re.match(r'.*Step \d+.*', rule_text):
                return  # Skip step separator rules

        # Filter out step headers and model output
        if isinstance(first_arg, str):
            # Skip step separators, model output headers, duration lines
            stripped = first_arg.strip()
            if (re.match(r'^.*Step \d+.*$', first_arg) or
                'Output message of the LLM:' in first_arg or
                re.match(r'^\[Step \d+:.*\]$', first_arg) or
                'Final answer:' in first_arg or  # Skip duplicate "Final answer:" line
                stripped in ['1', '2']):
                return  # Skip entirely

        # Handle Panel objects (tool calls, observations)
        if isinstance(first_arg, Panel) and hasattr(first_arg, 'renderable'):
            text_str = str(first_arg.renderable)

            # Skip model output panels
            if 'Output message of the LLM:' in text_str or '<tool_call>' in text_str:
                return

            # Reformat tool call panels to be compact
            match = re.search(r"Calling tool: '(\w+)' with arguments: \{[^:]+: '(.+?)'\}", text_str, re.DOTALL)
            if match:
                tool_name = match.group(1)
                arg_value = match.group(2)
                if tool_name == "final_answer":
                    first_arg = Panel(Text(arg_value))
                else:
                    first_arg = Panel(Text(f"{tool_name} {{{arg_value}}}"))
                args = (first_arg,) + args[1:]
            else:
                # Try with double quotes
                match = re.search(r'Calling tool: \'(\w+)\' with arguments: \{[^:]+: "(.+?)"\}', text_str, re.DOTALL)
                if match:
                    tool_name = match.group(1)
                    arg_value = match.group(2)
                    if tool_name == "final_answer":
                        first_arg = Panel(Text(arg_value))
                    else:
                        first_arg = Panel(Text(f"{tool_name} {{{arg_value}}}"))
                    args = (first_arg,) + args[1:]

    # Print the (potentially modified) output
    return _original_print(self, *args, **kwargs)

Console.print = _filtered_print
