#!/usr/bin/env python3
"""
Generate a large test log file with dummy errors for testing log filtering
"""
import random
from datetime import datetime, timedelta

# Sample log messages
INFO_MESSAGES = [
    "Server started successfully",
    "Connection established to database",
    "User authenticated successfully",
    "Cache cleared",
    "Configuration loaded",
    "Health check passed",
    "Request processed successfully",
    "Session created",
    "Data synchronized",
    "Backup completed",
]

DEBUG_MESSAGES = [
    "Processing request from client",
    "Query executed in 45ms",
    "Cache hit for key: user_123",
    "Loading configuration from file",
    "Initializing connection pool",
    "Parsing JSON payload",
    "Validating input parameters",
    "Computing hash for file",
    "Checking permissions",
    "Fetching data from cache",
]

WARNING_MESSAGES = [
    "Connection pool running low, current: 5/100",
    "Slow query detected: 2.5s",
    "Deprecated API endpoint called",
    "Cache miss rate high: 45%",
    "Memory usage above 80%",
    "Retry attempt 2/3 for failed request",
    "SSL certificate expires in 30 days",
    "API rate limit approaching: 95/100",
]

ERROR_MESSAGES = [
    "Failed to connect to database: Connection refused",
    "HTTP Error 400: Bad Request - Invalid JSON payload",
    "HTTP Error 500: Internal Server Error",
    "Exception: NullPointerException in module user_service",
    "Error 502: Bad Gateway - Upstream server not responding",
    "Fatal error: Out of memory",
    "Database query failed: Table 'users' doesn't exist",
    "Authentication failed: Invalid credentials",
    "File not found: /var/log/app.log",
    "Network timeout after 30s",
    "Critical: Failed to write to disk - Errno 28: No space left on device",
    "Unhandled exception in request handler",
]

STACK_TRACES = [
    """Traceback (most recent call last):
  File "/app/main.py", line 142, in handle_request
    result = process_data(request.body)
  File "/app/processor.py", line 67, in process_data
    return parser.parse(data)
  File "/app/parser.py", line 34, in parse
    raise ValueError("Invalid data format")
ValueError: Invalid data format""",

    """Traceback (most recent call last):
  File "/app/database.py", line 89, in execute_query
    cursor.execute(query)
  File "/usr/lib/python3.9/mysql/connector.py", line 234, in execute
    raise DatabaseError("Connection lost")
mysql.connector.errors.DatabaseError: Connection lost""",

    """java.lang.NullPointerException: Cannot invoke method on null object
    at com.example.service.UserService.getUser(UserService.java:45)
    at com.example.controller.UserController.handleRequest(UserController.java:78)
    at com.example.web.RequestHandler.process(RequestHandler.java:123)""",

    """Error: ECONNREFUSED
    at TcpConnectWrap.afterConnect [as oncomplete] (net.js:1148:16)
    at Protocol._enqueue (/node_modules/mysql/lib/protocol/Protocol.js:144:48)
    at Protocol.handshake (/node_modules/mysql/lib/protocol/Protocol.js:51:23)""",
]

def generate_timestamp(base_time, offset_seconds):
    """Generate a timestamp"""
    dt = base_time + timedelta(seconds=offset_seconds)
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

def generate_log_entry(level, message, timestamp):
    """Generate a single log entry"""
    return f"[{timestamp}] [{level:8s}] {message}"

def generate_test_log(filename="test_app.log", target_size_mb=2):
    """Generate a large test log file with errors"""
    print(f"Generating test log file: {filename}")
    print(f"Target size: {target_size_mb} MB")

    base_time = datetime.now() - timedelta(hours=24)
    current_size = 0
    target_size = target_size_mb * 1024 * 1024  # Convert to bytes
    line_count = 0
    error_count = 0

    with open(filename, 'w') as f:
        time_offset = 0

        while current_size < target_size:
            # Determine log level (80% INFO/DEBUG, 15% WARNING, 5% ERROR)
            rand = random.random()

            if rand < 0.60:  # 60% INFO
                level = "INFO"
                message = random.choice(INFO_MESSAGES)
            elif rand < 0.80:  # 20% DEBUG
                level = "DEBUG"
                message = random.choice(DEBUG_MESSAGES)
            elif rand < 0.95:  # 15% WARNING
                level = "WARNING"
                message = random.choice(WARNING_MESSAGES)
            else:  # 5% ERROR
                level = "ERROR"
                message = random.choice(ERROR_MESSAGES)
                error_count += 1

                # 30% chance to add a stack trace after error
                if random.random() < 0.3:
                    timestamp = generate_timestamp(base_time, time_offset)
                    error_line = generate_log_entry(level, message, timestamp)
                    f.write(error_line + "\n")
                    current_size += len(error_line) + 1
                    line_count += 1

                    # Add stack trace
                    stack_trace = random.choice(STACK_TRACES)
                    f.write(stack_trace + "\n")
                    current_size += len(stack_trace) + 1
                    line_count += stack_trace.count('\n') + 1

                    time_offset += random.uniform(0.1, 2.0)
                    continue

            timestamp = generate_timestamp(base_time, time_offset)
            log_line = generate_log_entry(level, message, timestamp)
            f.write(log_line + "\n")
            current_size += len(log_line) + 1
            line_count += 1

            # Increment time by 0.1 to 5 seconds
            time_offset += random.uniform(0.1, 5.0)

            # Progress indicator every 10000 lines
            if line_count % 10000 == 0:
                print(f"  Generated {line_count:,} lines, {current_size / 1024 / 1024:.2f} MB")

    final_size = current_size / 1024 / 1024
    print(f"\nLog file generated successfully!")
    print(f"  File: {filename}")
    print(f"  Size: {final_size:.2f} MB")
    print(f"  Lines: {line_count:,}")
    print(f"  Errors: {error_count:,}")
    print(f"  Error rate: {error_count / line_count * 100:.1f}%")

if __name__ == "__main__":
    import sys

    # Default values
    filename = "../test_app.log"
    size_mb = 0.025

    # Parse command line arguments
    if len(sys.argv) > 1:
        filename = sys.argv[1]
    if len(sys.argv) > 2:
        size_mb = float(sys.argv[2])

    generate_test_log(filename, size_mb)
    print(f"\nYou can now test with: python simple-proxy.py --log-file proxy.log")
    print(f"Then ask Claude to analyze: {filename}")