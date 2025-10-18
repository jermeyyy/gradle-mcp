# Gradle MCP Server

A Model Context Protocol (MCP) server that provides tools to interact with Gradle projects using the Gradle Wrapper.

## Features

- **list_projects** - List all Gradle projects in the workspace
- **list_project_tasks** - List available tasks for a specific project
- **run_task** - Execute Gradle tasks (build, test, assemble, etc.)
- **clean** - Clean build artifacts (separate from run_task for safety)

## Installation

### Requirements
- Python 3.10+
- FastMCP 2.0+
- Gradle project with wrapper (`gradlew`)

### Install

```bash
# Clone and install
git clone <repository-url>
cd gradle-mcp
uv sync

# Or with pip
pip install -e .
```

## Usage

### Start the Server

```bash
# Auto-detects gradlew in current directory
gradle-mcp

# Or run directly
python -m gradle_mcp.server
```

### Logging

The server uses FastMCP's built-in logging mechanism to send log messages back to MCP clients:

- **Tool invocations** - Logs when each tool is called with its parameters
- **Gradle output** - Debug-level logs of full stdout/stderr from Gradle task execution
- **Operation progress** - Info messages about projects found, tasks discovered, etc.
- **Success/errors** - Completion status and error details with structured data

**Log levels used:**
- `DEBUG` - Gradle stdout/stderr output (full build logs)
- `INFO` - Normal operations (tool calls, results, progress)
- `ERROR` - Task failures with error details

**Client handling:**
- Logs are sent through the MCP protocol to the client
- How clients display these logs depends on their implementation
- Development clients may show logs in real-time

### Progress Reporting

The server provides real-time progress updates when executing Gradle tasks:

- **Real-time parsing** - Parses Gradle wrapper output to extract actual progress percentages
- **Progress patterns** - Looks for patterns like `<============-> 93% EXECUTING [19s]` in Gradle output
- **MCP protocol** - Uses FastMCP's `ctx.report_progress()` to send updates via MCP protocol
- **Client display** - Clients can show live progress bars or percentage updates

**How it works:**
1. Gradle tasks run without `-q` (quiet) flag to output progress information
2. Server reads Gradle output line-by-line in real-time using `subprocess.Popen()`
3. Regex pattern `r'(\d+)%'` extracts percentage from lines containing progress indicators
4. Progress updates are sent asynchronously via `await ctx.report_progress(progress, total=100)`
5. Clients receive these updates and can display them to users

**Applies to:**
- `run_task` - Shows progress for any Gradle task execution
- `clean` - Shows progress for cleaning operations

### Error Reporting

When Gradle tasks fail, the server provides comprehensive error messages:

- **Intelligent parsing** - Backward search strategy to find actual error details:
  1. **Combines stdout and stderr** - Gradle splits output (task failures → stdout, summaries → stderr)
  2. Locates `FAILURE:` or `BUILD FAILED` markers in combined output
  3. Searches **backwards** from these markers to find the **first** failed task
  4. Captures everything from the first failed task onwards (all failures, violations, and summaries)
- **Complete error details** - Captures **all** error messages from **multiple** failed tasks with their specific violations
- **Smart fallback** - If no task failures found, includes up to 100 lines before `BUILD FAILED` for maximum context
- **Structured output** - Returns both the parsed error message and full stdout/stderr for debugging

**How it works:**
- Gradle outputs task execution and error details to **stdout** (e.g., `> Task :app:detekt FAILED` + violations)
- Gradle outputs failure summaries to **stderr** (e.g., `FAILURE: Build completed with 2 failures`)
- The parser combines both streams and searches backwards from summary markers to find all task failures
- This ensures all error details (detekt violations, compilation errors, test failures) are captured

**Error message examples:**

For multiple linting/analysis failures (detekt, ktlint, etc.):
```json
{
  "success": false,
  "error": "> Task :quo-vadis-core:detekt FAILED\n/path/GraphNavHost.kt:100:13: The function GraphNavHostContent appears to be too complex... [CyclomaticComplexMethod]\n/path/GraphNavHost.kt:238:27: This expression contains a magic number... [MagicNumber]\n...\n\n> Task :composeApp:detekt FAILED\n/path/DetailScreen.kt:52:5: The function DetailScreen is too long (137). The maximum length is 60. [LongMethod]\n...\n\nFAILURE: Build completed with 2 failures.\n\n1: Task failed with an exception.\n-----------\n* What went wrong:\nExecution failed for task ':quo-vadis-core:detekt'.\n> Analysis failed with 5 issues.\n...\n\n2: Task failed with an exception.\n-----------\n* What went wrong:\nExecution failed for task ':composeApp:detekt'.\n> Analysis failed with 6 issues.\n...\n\nBUILD FAILED in 1s",
}
```

For compilation failures:
```json
{
  "success": false,
  "error": "FAILURE: Build failed with an exception.\n\n* What went wrong:\nExecution failed for task ':app:compileJava'.\n> Compilation failed; see the compiler error output for details.",
}
```

The `error` field contains the most relevant failure information starting from where the actual errors occur, while `stdout` and `stderr` contain complete logs (also sent via DEBUG logging).

- See your MCP client's documentation for log viewing
- Enable debug logging in your client to see Gradle output

### Environment Variables

- `GRADLE_PROJECT_ROOT` - Path to Gradle project (default: current directory)
- `GRADLE_WRAPPER` - Path to gradlew script (default: auto-detected)

```bash
# Custom project location
export GRADLE_PROJECT_ROOT=/path/to/project
gradle-mcp

# Custom wrapper location
export GRADLE_WRAPPER=/path/to/custom/gradlew
gradle-mcp
```

## MCP Tools

### list_projects()
List all Gradle projects in the workspace.

**Returns:** List of projects with name and path

### list_project_tasks(project: str | None)
List tasks for a specific project.

**Parameters:**
- `project` - Project path (e.g., `:app`, or `:` / `None` / `""` for root)

**Returns:** List of tasks with name, description, and group

### run_task(task: str, args: list[str] | None)
Run a Gradle task. Cannot run cleaning tasks (use `clean` tool instead).

**Parameters:**
- `task` - Task name with optional project path (e.g., `:app:build`, `build`)
- `args` - Additional Gradle arguments (e.g., `["-x", "test"]`)

**Returns:** Success status and error message if failed

### clean(project: str | None)
Clean build artifacts for a project.

**Parameters:**
- `project` - Project path (e.g., `:app`, or `:` / `None` / `""` for root)

**Returns:** Success status and error message if failed

## Examples

### Using with MCP Client

```python
# List all projects
list_projects()

# List tasks for app project
list_project_tasks(project=":app")

# Build the app
run_task(task=":app:build")

# Run tests with skip integration
run_task(task=":app:test", args=["-x", "integration"])

# Clean the app
clean(project=":app")
```

### As Python Module

```python
from gradle_mcp.gradle import GradleWrapper

gradle = GradleWrapper("/path/to/gradle/project")

# List projects
projects = gradle.list_projects()
for project in projects:
    print(f"Project: {project.name}")

# List tasks
tasks = gradle.list_tasks(":app")
for task in tasks:
    print(f"  {task.name}: {task.description}")

# Run task
result = gradle.run_task(":app:build")
if result["success"]:
    print("Build succeeded!")
else:
    print(f"Build failed: {result['error']}")

# Clean
result = gradle.clean(":app")
```

## Development

```bash
# Install dev dependencies
uv sync --all-extras

# Run tests
pytest

# Run implementation tests
python test_implementation.py
```

## Architecture

### Safety Design
- `run_task` blocks cleaning tasks (clean, cleanBuild, etc.)
- `clean` tool is the only way to run cleaning operations
- Prevents accidental cleanup during build operations

### Task Execution
- Uses Gradle wrapper for compatibility
- `-q` flag for quiet output (errors only)
- `--no-build-cache` for clean execution
- Progress reporting via FastMCP context

## License

[Add your license here]


### Code Quality

```bash
# Format code
black src/

# Lint code
ruff check src/

# Type checking
mypy src/
```

### Running Tests

```bash
pytest tests/
```

## Project Structure

```
gradle-mcp/
├── src/gradle_mcp/
│   ├── __init__.py          # Package initialization
│   ├── server.py            # MCP server implementation
│   └── gradle.py            # Gradle wrapper interface
├── tests/                   # Test suite
├── pyproject.toml          # Project configuration
└── README.md               # This file
```

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
