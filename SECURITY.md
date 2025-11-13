# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Security Considerations

⚠️ **Important:** This tool is designed for **local DevOps automation** in trusted environments.

### Known Security Limitations

1. **Shell Command Execution**: Uses `shell=True` for command execution
   - Can execute arbitrary shell commands
   - No input sanitization or command whitelisting
   - Full access to file system and shell commands

2. **No Sandboxing**: The agent runs with full user permissions
   - Can read/write any files the user has access to
   - Can execute any commands the user can run
   - No resource limits or quotas

3. **Model Trust**: Relies on the AI model's decision-making
   - Model could potentially be misled by crafted inputs
   - No guaranteed safety for destructive operations
   - Approval mode (`--require-approval`) is strongly recommended

### Recommended Security Measures

**For Personal Use:**
- Always use `--require-approval` flag for sensitive operations
- Review all tool calls before approval
- Run in isolated environments when testing
- Never run with elevated privileges unless absolutely necessary

**For Production Use:**
- Deploy in containerized environments with limited permissions
- Implement command whitelisting
- Add proper input validation
- Use dedicated service accounts with minimal privileges
- Enable audit logging for all operations
- Consider network isolation

**For Multi-User Environments:**
- **DO NOT deploy this tool in multi-user environments without significant security hardening**
- Implement authentication and authorization
- Add rate limiting
- Isolate user sessions
- Implement comprehensive audit trails

## Reporting a Vulnerability

If you discover a security vulnerability, please help us protect our users:

### DO:
1. **Email security concerns** to: [security contact email - to be added]
2. **Provide detailed information**:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if available)
3. **Allow time for response**: We aim to respond within 48 hours
4. **Keep it confidential**: Please don't publicly disclose until we've had a chance to address it

### DON'T:
- Publicly disclose the vulnerability before it's patched
- Exploit the vulnerability beyond what's necessary to demonstrate it
- Access other users' data or systems

## Security Update Process

1. **Report received**: We acknowledge within 48 hours
2. **Validation**: We verify and assess the vulnerability
3. **Fix development**: We develop and test a patch
4. **Release**: We release a security update
5. **Disclosure**: We publish a security advisory

## Security Best Practices for Users

### Using Approval Mode
Always use approval mode for sensitive operations:
```bash
python agent.py --require-approval "Your task here"
```

### Reviewing Tool Calls
Before approving any tool call, verify:
- The command is what you expect
- The arguments are correct
- You understand what it will do
- You have backups if it could cause data loss

### Environment Isolation
Run in isolated environments:
```bash
# Docker example (once Dockerfile is available)
docker run --rm -it ollama-devops "Your task"
```

### Least Privilege
- Don't run as root unless absolutely necessary
- Create dedicated user accounts for automation
- Limit file system access where possible

## Audit and Monitoring

While the tool doesn't have built-in audit logging, you can:

1. **Enable verbose mode** to see all operations:
   ```bash
   python agent.py --verbose "Your task"
   ```

2. **Log all sessions** to a file:
   ```bash
   python agent.py "Your task" 2>&1 | tee agent-$(date +%Y%m%d-%H%M%S).log
   ```

3. **Monitor system logs** for unexpected activity

## Responsible Disclosure

We appreciate security researchers who:
- Follow responsible disclosure practices
- Give us reasonable time to fix issues
- Don't exploit vulnerabilities maliciously

We commit to:
- Acknowledge reports promptly
- Keep reporters informed of progress
- Credit researchers (with permission)
- Release fixes in a timely manner

## Contact

For security issues: [security contact - to be added]
For general issues: GitHub Issues

---

Thank you for helping keep Ollama DevOps Agent and its users safe!
