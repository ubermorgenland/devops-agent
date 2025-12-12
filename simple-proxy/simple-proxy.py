#!/usr/bin/env python3

"""
Simple Middleware Proxy for Claude Code (Python Version)

This script acts as a proxy between Claude Code and api.anthropic.com
Usage:
    python simple-proxy.py [--log-file proxy.log]

Then in another terminal:
    export ANTHROPIC_BASE_URL="http://127.0.0.1:3456"
    claude "your prompt"
"""
import os
import sys
import json
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import http.client
from datetime import datetime
import tempfile
import re

# Add parent directory to sys.path to import ollama_backend
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ollama_backend import OllamaChat

PORT = 3456
ANTHROPIC_API = 'api.anthropic.com'
LOG_FILE = None
log_file_handle = None

# Track filtered files: original_path -> filtered_path
filtered_files = {}


def log(message):
    """Log to both console and file if configured"""
    print(message, flush=True)
    if log_file_handle:
        log_file_handle.write(message + '\n')
        log_file_handle.flush()


class ProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        """Override to use custom logging"""
        pass

    def do_GET(self):
        self._proxy_request()

    def do_POST(self):
        self._proxy_request()

    def do_PUT(self):
        self._proxy_request()

    def do_DELETE(self):
        self._proxy_request()

    def do_PATCH(self):
        self._proxy_request()

    def _proxy_request(self):
        global filtered_files

        # Log request
        log(f"\n[{datetime.utcnow().isoformat()}Z] {self.command} {self.path}")
        # log(f"Headers: {json.dumps(dict(self.headers), indent=2)}")

        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else b''

        # Intercept requests to inject instructions about filtered files
        if body and self.command == 'POST' and '/v1/messages' in self.path:
            try:
                parsed = json.loads(body.decode('utf-8'))

                # Check if this request contains tool_results for filtered files
                if 'messages' in parsed and filtered_files:
                    files_in_this_request = []

                    # Look for tool_result blocks
                    for message in parsed.get('messages', []):
                        if message.get('role') == 'user':
                            content = message.get('content', [])
                            if isinstance(content, list):
                                for block in content:
                                    if isinstance(block, dict) and block.get('type') == 'tool_result':
                                        # This message contains a tool result
                                        # Check if it was for a filtered file by checking our tracked files
                                        for orig_path, filt_path in filtered_files.items():
                                            if filt_path in str(block):
                                                files_in_this_request.append((orig_path, filt_path))

                    # If we found filtered files in this request, append instructions
                    if files_in_this_request:
                        instructions = "\n\nIMPORTANT: The following files were automatically filtered to show only relevant content:\n"
                        for orig, filt in files_in_this_request:
                            instructions += f"- {orig} → {filt} (filtered)\n"
                        instructions += "\nYou must ONLY analyze the filtered versions. Do NOT attempt to read the original files. The filtered files contain AI-summarized content focusing on errors, warnings, and important events."

                        # Append to the last user message or create a new one
                        appended = False
                        for message in reversed(parsed['messages']):
                            if message.get('role') == 'user':
                                content = message.get('content', '')
                                if isinstance(content, str):
                                    message['content'] = content + instructions
                                    appended = True
                                    break
                                elif isinstance(content, list):
                                    # Append as a text block
                                    content.append({
                                        'type': 'text',
                                        'text': instructions
                                    })
                                    appended = True
                                    break

                        if appended:
                            log(f"📝 Appended filter instructions for {len(files_in_this_request)} file(s)")
                            body = json.dumps(parsed).encode('utf-8')

            except Exception as e:
                log(f"Error injecting filter instructions: {str(e)}")
                pass

        # Prepare headers for forwarding
        forward_headers = {}
        for key, value in self.headers.items():
            # Skip hop-by-hop headers and content-length (we'll set it ourselves)
            if key.lower() not in ['connection', 'keep-alive', 'proxy-authenticate',
                                    'proxy-authorization', 'te', 'trailers',
                                    'transfer-encoding', 'upgrade', 'host', 'content-length']:
                forward_headers[key] = value

        # Always set Content-Length based on actual body size
        if body:
            forward_headers['Content-Length'] = str(len(body))
        else:
            forward_headers['Content-Length'] = '0'

        # Set the correct host header
        forward_headers['Host'] = ANTHROPIC_API

        try:
            # Create HTTPS connection
            conn = http.client.HTTPSConnection(ANTHROPIC_API, timeout=600)

            # Log what we're sending
            log(f"Forwarding to: https://{ANTHROPIC_API}{self.path}")
            log(f"Forward headers: {json.dumps(forward_headers, indent=2)}")
            if body:
                log(f"Body length: {len(body)} bytes")

            # Send request
            conn.request(
                method=self.command,
                url=self.path,
                body=body,
                headers=forward_headers
            )

            # Get response
            response = conn.getresponse()

            log(f"Response status: {response.status}")
            log(f"Response headers: {json.dumps(dict(response.headers), indent=2)}")

            # Send response status and headers to client
            self.send_response(response.status)

            # Forward response headers
            for header, value in response.headers.items():
                # Skip hop-by-hop headers
                if header.lower() not in ['connection', 'keep-alive', 'transfer-encoding']:
                    self.send_header(header, value)

            self.end_headers()

            # Stream response body and intercept Read tool calls
            is_streaming = 'text/event-stream' in response.headers.get('Content-Type', '')

            # For non-streaming, buffer entire response to modify it
            if not is_streaming:
                response_body = response.read()

                # Try to parse and modify response
                try:
                    response_data = json.loads(response_body.decode('utf-8'))
                    modified = intercept_read_tool_calls(response_data)

                    if modified:
                        response_body = json.dumps(response_data).encode('utf-8')
                        log(f"Modified non-streaming response")

                except:
                    pass  # If not JSON or error, send as-is

                self.wfile.write(response_body)

            else:
                # For streaming, we need to buffer the entire response to modify tool_use blocks
                # because tool input comes in multiple delta events
                log("Buffering streaming response to intercept tool calls...")

                streaming_buffer = b""
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    streaming_buffer += chunk

                # Parse all SSE events
                events = []
                lines = streaming_buffer.decode('utf-8', errors='replace').split('\n')

                for line in lines:
                    if line.startswith('data:'):
                        try:
                            data = json.loads(line[5:].strip())
                            events.append(data)
                            # Debug: log event types
                            event_type = data.get('type', 'unknown')
                            if event_type in ['content_block_start', 'content_block_delta', 'content_block_stop']:
                                log(f"  Parsed event: {event_type}")
                                if event_type == 'content_block_start':
                                    cb = data.get('content_block', {})
                                    log(f"    Block type: {cb.get('type')}, name: {cb.get('name', 'N/A')}")
                        except Exception as e:
                            log(f"  Error parsing SSE line: {e}")
                            pass

                log(f"Total events parsed: {len(events)}")

                # Build complete tool_use blocks from events
                tool_uses = {}  # {block_index: {type, name, input}}

                for event in events:
                    event_type = event.get('type', '')

                    if event_type == 'content_block_start':
                        content_block = event.get('content_block', {})
                        if content_block.get('type') == 'tool_use':
                            block_index = event.get('index', 0)
                            tool_uses[block_index] = {
                                'name': content_block.get('name'),
                                'input_partial': ''
                            }
                            log(f"  Tool_use detected at index {block_index}: {content_block.get('name')}")

                    elif event_type == 'content_block_delta':
                        block_index = event.get('index', 0)
                        delta = event.get('delta', {})
                        if delta.get('type') == 'input_json_delta':
                            # Accumulate input JSON
                            partial_json = delta.get('partial_json', '')
                            if block_index in tool_uses:
                                tool_uses[block_index]['input_partial'] += partial_json

                # Parse accumulated inputs and check for Read tool calls
                for block_id, tool_data in tool_uses.items():
                    if tool_data.get('name') == 'Read' and 'input_partial' in tool_data:
                        try:
                            tool_input = json.loads(tool_data['input_partial'])
                            file_path = tool_input.get('file_path', '')

                            if file_path and os.path.exists(file_path):
                                file_size = os.path.getsize(file_path)
                                min_file_size = 1 * 1024

                                if file_size >= min_file_size:
                                    log(f"🔍 Found Read tool call for large file: {file_path} ({file_size} bytes)")

                                    # Read and filter file
                                    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                                        content = f.read()

                                    filtered = filter_log_file_content(content, file_path)

                                    # Create filtered file
                                    tmp_dir = tempfile.gettempdir()
                                    filtered_filename = f"filtered_{os.path.basename(file_path)}"
                                    filtered_path = os.path.join(tmp_dir, filtered_filename)

                                    with open(filtered_path, 'w', encoding='utf-8') as f:
                                        f.write(f"# FILTERED - Original: {file_path} ({file_size} bytes)\n")
                                        f.write(f"# Showing only errors, warnings, and important content\n")
                                        f.write("-" * 80 + "\n\n")
                                        f.write(filtered)

                                    # Update input with filtered path
                                    tool_input['file_path'] = filtered_path
                                    tool_data['modified_input'] = json.dumps(tool_input)

                                    # Track this filtered file globally
                                    filtered_files[file_path] = filtered_path

                                    log(f"✅ Will replace with filtered file: {filtered_path}")
                        except Exception as e:
                            log(f"Error parsing tool input: {e}")

                # Re-stream events, modifying Read tool inputs
                current_tool_index = -1
                current_tool_data = None
                sent_input_json = {}

                for line in lines:
                    if line.startswith('data:'):
                        try:
                            event = json.loads(line[5:].strip())
                            event_type = event.get('type', '')

                            if event_type == 'content_block_start':
                                content_block = event.get('content_block', {})
                                if content_block.get('type') == 'tool_use':
                                    current_tool_index = event.get('index', 0)
                                    current_tool_data = tool_uses.get(current_tool_index)
                                    sent_input_json[current_tool_index] = False

                            elif event_type == 'content_block_delta' and current_tool_data:
                                delta = event.get('delta', {})
                                if delta.get('type') == 'input_json_delta' and 'modified_input' in current_tool_data:
                                    # Replace with modified input (send it all at once on first delta)
                                    if not sent_input_json.get(current_tool_index, False):
                                        delta['partial_json'] = current_tool_data['modified_input']
                                        event['delta'] = delta
                                        line = 'data: ' + json.dumps(event)
                                        sent_input_json[current_tool_index] = True
                                        log(f"  Sent modified input in first delta")
                                    else:
                                        # Send empty deltas for subsequent events to maintain stream structure
                                        delta['partial_json'] = ''
                                        event['delta'] = delta
                                        line = 'data: ' + json.dumps(event)
                                        log(f"  Sent empty delta to maintain stream")

                            elif event_type == 'content_block_stop':
                                current_tool_index = -1
                                current_tool_data = None

                        except:
                            pass

                    self.wfile.write((line + '\n').encode('utf-8'))

            conn.close()
            log("Request completed\n")

        except Exception as e:
            log(f"Proxy error: {str(e)}")
            # Only try to send error response if we haven't sent headers yet
            # (Avoid broken pipe errors when client disconnects or headers already sent)
            try:
                self.send_response(502)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                error_response = json.dumps({
                    'error': 'Proxy Error',
                    'message': str(e)
                })
                self.wfile.write(error_response.encode('utf-8'))
            except Exception as send_error:
                # Client disconnected or headers already sent - just log it
                log(f"Could not send error response to client: {str(send_error)}")

# Model backend - using merged model (LoRA weights merged into base model for faster inference)
ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
ollama_endpoint = f"{ollama_host}/api/chat" if not ollama_host.endswith("/api/chat") else ollama_host
model = OllamaChat(model="qwen3:8b", endpoint=ollama_endpoint)


def intercept_read_tool_calls(response_data: dict) -> bool:
    """
    Intercept Read tool calls in API response and replace large file paths
    with filtered versions.

    Args:
        response_data: The API response data (dict)

    Returns:
        True if modified, False otherwise
    """
    modified = False

    try:
        # Check if response has content blocks
        content = response_data.get('content', [])
        if not isinstance(content, list):
            return False

        for block in content:
            if not isinstance(block, dict):
                continue

            # Look for tool_use blocks with name="Read"
            if block.get('type') == 'tool_use' and block.get('name') == 'Read':
                tool_input = block.get('input', {})
                file_path = tool_input.get('file_path', '')

                if not file_path or not os.path.exists(file_path):
                    continue

                # Check file size
                try:
                    file_size = os.path.getsize(file_path)
                    min_file_size = 1 * 1024  # 50KB

                    if file_size < min_file_size:
                        log(f"File {file_path} is small ({file_size} bytes), skipping")
                        continue

                    log(f"🔍 Detected Read tool call for large file: {file_path} ({file_size} bytes)")

                    # Read and filter the file
                    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                        content = f.read()

                    # Filter content
                    filtered = filter_log_file_content(content)

                    # Create filtered file in tmp
                    tmp_dir = tempfile.gettempdir()
                    filename = os.path.basename(file_path)
                    filtered_filename = f"filtered_{filename}"
                    filtered_path = os.path.join(tmp_dir, filtered_filename)

                    with open(filtered_path, 'w', encoding='utf-8') as f:
                        f.write(f"# FILTERED - Original: {file_path} ({file_size} bytes)\n")
                        f.write(f"# Showing only errors, warnings, and important content\n")
                        f.write("-" * 80 + "\n\n")
                        f.write(filtered)

                    # Replace file_path in tool_use
                    tool_input['file_path'] = filtered_path
                    modified = True

                    log(f"✅ Replaced with filtered file: {filtered_path} ({len(filtered)} bytes)")

                except Exception as file_error:
                    log(f"Error processing file {file_path}: {str(file_error)}")
                    continue

    except Exception as e:
        log(f"Error in intercept_read_tool_calls: {str(e)}")

    return modified


def filter_log_file_content(content: str, original_file_path: str = "") -> str:
    """
    Use AI to summarize log file content, focusing on errors and important events.

    Args:
        content: The full file content
        original_file_path: Path to the original file (for logging)

    Returns:
        Summarized content or original if not a log file
    """
    try:
        original_size = len(content)

        # First, check if this looks like a log file
        check_prompt = f"""Analyze the following file content and determine if it's a log file.
A log file typically contains:
- Timestamps
- Log levels (INFO, ERROR, WARNING, DEBUG, etc.)
- Structured log entries
- System/application events

File content (first 2000 chars):
{content[:2000]}

Respond with JSON:
{{"is_log_file": true/false, "reason": "brief explanation"}}"""

        response = model.generate([{"role": "user", "content": check_prompt}])
        response_text = response.content if hasattr(response, 'content') else str(response)

        # Parse JSON response
        json_match = re.search(r'{.*}', response_text, re.DOTALL)
        if not json_match:
            log(f"Could not determine if file is a log, treating as log file")
            is_log_file = True
        else:
            result = json.loads(json_match.group())
            is_log_file = result.get('is_log_file', True)
            reason = result.get('reason', 'N/A')
            log(f"AI model says is_log_file={is_log_file}: {reason}")

        if not is_log_file:
            log(f"File does not look like a log file, skipping summarization")
            return content

        # Summarize the log file
        summarize_prompt = f"""Analyze this log file and create a concise summary focusing on:
1. Errors and exceptions
2. Warnings and critical issues
3. Important events or state changes
4. Any patterns or recurring issues

Keep the summary under 500 lines. Include actual log lines for important errors/warnings.

Log file content:
{content}

Provide a structured summary."""

        log(f"Asking AI to summarize log file ({original_size} bytes)...")
        summary_response = model.generate([{"role": "user", "content": summarize_prompt}])
        summary = summary_response.content if hasattr(summary_response, 'content') else str(summary_response)

        filtered_size = len(summary)
        log(f"✅ AI summarized log: {original_size} bytes -> {filtered_size} bytes")

        return summary

    except Exception as e:
        log(f"Error using AI to filter content: {str(e)}")
        log("Falling back to original content")
        return content


def filter_log_content(content: str) -> str:
    """
    Filter log content to keep only important parts (errors, warnings, etc.)

    Args:
        content: The full log content from Read tool result

    Returns:
        Filtered content with only important parts
    """
    try:
        lines = content.split('\n')
        important_lines = []

        # Keywords that indicate important content
        error_keywords = ['error', 'exception', 'traceback', 'warning', 'fatal', 'critical',
                        'fail', 'stack trace', '400', '500', '502', '503', 'errno', 'broken pipe']

        log(f"Filtering log content: {len(lines)} lines, {len(content)} bytes")

        for i, line in enumerate(lines):
            line_lower = line.lower()

            # Check if line contains error keywords
            if any(keyword in line_lower for keyword in error_keywords):
                # Include context: 2 lines before and 5 lines after
                start = max(0, i - 2)
                end = min(len(lines), i + 6)
                context = lines[start:end]
                important_lines.extend(context)

                # Add separator if not at the end
                if i + 6 < len(lines):
                    important_lines.append("...")

        if not important_lines:
            log("No errors/warnings found, keeping first and last 100 lines")
            # If no errors found, keep first and last parts
            important_lines = lines[:100] + ["...", "... (middle content skipped) ...", "..."] + lines[-100:]

        # Remove duplicates while preserving order
        seen = set()
        filtered_lines = []
        for line in important_lines:
            if line not in seen or line == "...":
                filtered_lines.append(line)
                seen.add(line)

        # Add header
        header = [
            "# FILTERED LOG CONTENT - Showing only errors, warnings, and important content",
            f"# Original: {len(lines)} lines, {len(content)} bytes",
            f"# Filtered: {len(filtered_lines)} lines",
            "-" * 80,
            ""
        ]

        filtered_content = '\n'.join(header + filtered_lines)
        log(f"Filtered to {len(filtered_lines)} lines, {len(filtered_content)} bytes")

        return filtered_content

    except Exception as e:
        log(f"Error filtering log content: {str(e)}")
        return content  # Return original if filtering fails

def run_server(port, log_file):
    global LOG_FILE, log_file_handle

    LOG_FILE = log_file
    if log_file:
        log_file_handle = open(log_file, 'a', buffering=1)
        log(f"📝 Logging to file: {log_file}\n")

    server = HTTPServer(('127.0.0.1', port), ProxyHandler)

    print(f"""
🚀 Simple Claude Code Proxy Server Started!

Listening on: http://127.0.0.1:{port}
Forwarding to: https://{ANTHROPIC_API}

To use with Claude Code, run in another terminal:
  export ANTHROPIC_BASE_URL="http://127.0.0.1:{port}"
  claude "your prompt"

Press Ctrl+C to stop
""")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\nShutting down proxy server...")
        server.shutdown()
        if log_file_handle:
            log_file_handle.close()
        print("Server closed")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Simple Claude Code Proxy')
    parser.add_argument('--log-file', type=str, help='Log file path')
    parser.add_argument('--port', type=int, default=PORT, help=f'Port to listen on (default: {PORT})')

    args = parser.parse_args()

    run_server(args.port, args.log_file)