"""Gradle wrapper interface for executing Gradle commands."""

import subprocess
import json
import re
import asyncio
from pathlib import Path
from typing import Optional, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from fastmcp import Context


@dataclass
class GradleProject:
    """Represents a Gradle project."""
    name: str
    path: str
    description: Optional[str] = None


@dataclass
class GradleTask:
    """Represents a Gradle task."""
    name: str
    project: str
    description: Optional[str] = None
    group: Optional[str] = None


class GradleWrapper:
    """Interface for executing Gradle commands using the Gradle wrapper."""

    # Cleaning task patterns that should not be allowed in run_task
    CLEANING_TASK_PATTERNS = [
        r"^clean.*",
        r".*clean$",
        r"^cleanBuild.*",
        r"^cleanTest.*",
    ]

    # Allow-list of safe Gradle arguments that can be passed to run_task
    # These are carefully selected to avoid command injection vulnerabilities
    SAFE_GRADLE_ARGS = {
        # Logging options
        '--debug', '-d',
        '--info', '-i',
        '--warn', '-w',
        '--quiet', '-q',
        '--stacktrace', '-s',
        '--full-stacktrace', '-S',
        '--scan',
        '--no-scan',
        
        # Performance options
        '--build-cache',
        '--no-build-cache',
        '--configure-on-demand',
        '--no-configure-on-demand',
        '--max-workers',
        '--parallel',
        '--no-parallel',
        
        # Execution options
        '--continue',
        '--dry-run', '-m',
        '--refresh-dependencies',
        '--rerun-tasks',
        '--profile',
        
        # Task exclusion (safe as it only limits what runs)
        '-x', '--exclude-task',
        
        # Daemon options
        '--daemon',
        '--no-daemon',
        '--foreground',
        '--stop',
        '--status',
    }
    
    # Dangerous arguments that should never be allowed
    # These can lead to arbitrary code execution or file system access
    DANGEROUS_GRADLE_ARGS = {
        '--init-script', '-I',  # Can execute arbitrary Groovy/Kotlin code
        '--project-prop', '-P',  # Can inject properties
        '--system-prop', '-D',  # Can set system properties
        '--settings-file', '-c',  # Can load arbitrary settings
        '--build-file', '-b',  # Can load arbitrary build files
        '--gradle-user-home', '-g',  # Can access arbitrary directories
        '--project-dir', '-p',  # Can access arbitrary directories
        '--include-build',  # Can include arbitrary builds
        '--write-verification-metadata',  # Can write files to arbitrary locations
    }

    def __init__(self, project_root: Optional[str] = None) -> None:
        """Initialize Gradle wrapper.

        Args:
            project_root: Root directory of the Gradle project. Defaults to current directory.
        """
        self.project_root = Path(project_root or ".")
        self.wrapper_script = self._find_wrapper_script()

    def _find_wrapper_script(self) -> Path:
        """Find the Gradle wrapper script.

        Returns:
            Path to the gradlew script.

        Raises:
            FileNotFoundError: If Gradle wrapper is not found.
        """
        gradle_wrapper = self.project_root / "gradlew"
        if not gradle_wrapper.exists():
            raise FileNotFoundError(
                f"Gradle wrapper not found at {gradle_wrapper}. "
                "Please ensure gradlew script exists in the project root."
            )
        return gradle_wrapper

    def _is_cleaning_task(self, task: str) -> bool:
        """Check if a task is a cleaning task.

        Args:
            task: Task name to check.

        Returns:
            True if the task is a cleaning task, False otherwise.
        """
        task_lower = task.lower()
        for pattern in self.CLEANING_TASK_PATTERNS:
            if re.match(pattern, task_lower):
                return True
        return False

    def _validate_gradle_args(self, args: list[str]) -> None:
        """Validate that all provided Gradle arguments are safe.
        
        This method prevents command injection by ensuring that only safe,
        pre-approved arguments can be passed to Gradle. Any dangerous arguments
        that could lead to arbitrary code execution or file system access are blocked.
        
        Args:
            args: List of arguments to validate.
            
        Raises:
            ValueError: If any dangerous or unknown arguments are detected.
        """
        if not args:
            return
            
        i = 0
        while i < len(args):
            arg = args[i]
            
            # Check if this is a dangerous argument
            if arg in self.DANGEROUS_GRADLE_ARGS:
                raise ValueError(
                    f"Argument '{arg}' is not allowed due to security concerns. "
                    f"It could enable arbitrary code execution or unauthorized file access."
                )
            
            # Check for dangerous arguments that might be prefix of a longer string
            # This catches both --arg=value and -Xvalue patterns
            for dangerous in self.DANGEROUS_GRADLE_ARGS:
                if arg.startswith(dangerous + '=') or (len(dangerous) == 2 and arg.startswith(dangerous) and len(arg) > 2):
                    raise ValueError(
                        f"Argument '{arg}' is not allowed due to security concerns. "
                        f"It could enable arbitrary code execution or unauthorized file access."
                    )
            
            # Check if this is a safe argument
            if arg in self.SAFE_GRADLE_ARGS:
                # Some arguments take values, skip the next arg if it doesn't start with -
                if arg in {'--max-workers', '-x', '--exclude-task'}:
                    i += 1  # Skip next arg (the value)
                    if i < len(args) and args[i].startswith('-'):
                        i -= 1  # Actually it was another flag, don't skip
                i += 1
                continue
            
            # Check for arguments with = syntax (e.g., --max-workers=4)
            base_arg = arg.split('=')[0]
            if base_arg in self.SAFE_GRADLE_ARGS:
                i += 1
                continue
            
            # Unknown argument - reject it for safety
            raise ValueError(
                f"Argument '{arg}' is not in the allow-list of safe Gradle arguments. "
                f"Allowed arguments are: {', '.join(sorted(self.SAFE_GRADLE_ARGS))}"
            )

    def _extract_error_message(self, stdout: str, stderr: str, default_message: str = "Task failed") -> str:
        """Extract comprehensive error message from Gradle output.
        
        This method searches for failed tasks and captures all error details
        by searching backwards from FAILURE: or BUILD FAILED markers.
        
        Args:
            stdout: Standard output from Gradle.
            stderr: Standard error from Gradle.
            default_message: Default message if no error markers found.
            
        Returns:
            Extracted error message with full context.
        """
        # Combine stdout and stderr since Gradle splits output between them
        # Task failures and error details go to stdout
        # FAILURE: summary goes to stderr
        combined_output = stdout + "\n" + stderr if stdout and stderr else (stdout or stderr or default_message)
        error_lines = combined_output.strip().split('\n')
        
        # Strategy: Find where actual errors start by searching backwards
        # Gradle output structure for failures:
        # 1. Failed tasks with their errors appear first (in stdout)
        # 2. Then "FAILURE:" section with summaries (in stderr)
        # 3. Finally "BUILD FAILED" summary (in stderr)
        
        # We want to capture from the first failed task onwards
        
        first_failure_idx = -1
        failure_marker_idx = -1
        build_failed_idx = -1
        
        # Find key markers
        for i, line in enumerate(error_lines):
            if 'FAILED' in line and '> Task' in line:
                # Track first failed task
                if first_failure_idx == -1:
                    first_failure_idx = i
            if 'FAILURE:' in line or '* What went wrong:' in line:
                if failure_marker_idx == -1:
                    failure_marker_idx = i
            if 'BUILD FAILED' in line:
                build_failed_idx = i
        
        # If we found FAILURE: or BUILD FAILED, search backwards for the first task failure
        if failure_marker_idx >= 0 or build_failed_idx >= 0:
            marker_idx = failure_marker_idx if failure_marker_idx >= 0 else build_failed_idx
            
            # Search backwards from the marker to find ALL failed tasks
            # Keep updating first_failure_idx to get the earliest one
            for i in range(marker_idx - 1, -1, -1):
                line = error_lines[i]
                if 'FAILED' in line and '> Task' in line:
                    # Update to capture the earliest failed task
                    first_failure_idx = i
                # Stop if we hit successful/skipped tasks (but not failed ones)
                elif '> Task' in line and 'FAILED' not in line:
                    # Hit a non-failed task (UP-TO-DATE, NO-SOURCE, FROM-CACHE, etc.)
                    # Stop searching backwards
                    break
                elif any(marker in line for marker in ['Configuration cache', 'BUILD SUCCESSFUL']):
                    # Hit build start indicators (but NOT "Reusing configuration" which appears at the top)
                    break
        
        # Use the first failure we found
        if first_failure_idx >= 0:
            return '\n'.join(error_lines[first_failure_idx:])
        # Fallback: include substantial context before BUILD FAILED or from the end
        elif build_failed_idx >= 0:
            start_idx = max(0, build_failed_idx - 100)
            return '\n'.join(error_lines[start_idx:])
        else:
            # Last resort: include last 50 lines
            return '\n'.join(error_lines[-50:]) if len(error_lines) > 50 else combined_output

    def list_projects(self) -> list[GradleProject]:
        """List all Gradle projects in the workspace.

        Returns:
            List of GradleProject objects.

        Raises:
            subprocess.CalledProcessError: If Gradle command fails.
        """
        try:
            result = subprocess.run(
                [str(self.wrapper_script), "projects", "-q"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                check=True,
            )

            projects = []
            root_added = False
            
            for line in result.stdout.split("\n"):
                line = line.strip()
                
                # Add root project (only once)
                if "Root project" in line and not root_added:
                    projects.append(
                        GradleProject(
                            name=":",
                            path=str(self.project_root),
                            description="Root project"
                        )
                    )
                    root_added = True
                    continue
                
                # Look for subproject lines like "+--- Project ':app'" or "Project ':app'"
                # But skip if it's the root project line we already handled
                if "Project '" in line and "Root project" not in line:
                    # Extract project name from various formats
                    match = re.search(r"Project '([^']+)'", line)
                    if match:
                        project_name = match.group(1)
                        # Skip root project if it appears again
                        if project_name != ":":
                            projects.append(
                                GradleProject(
                                    name=project_name,
                                    path=str(self.project_root),
                                )
                            )

            return projects
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to list projects: {e.stderr}"
            ) from e

    def list_tasks(self, project: str = ":") -> list[GradleTask]:
        """List all available tasks for a specific Gradle project.

        Args:
            project: Project name (e.g., ':app'). Use ':' or empty string for root project.

        Returns:
            List of GradleTask objects.

        Raises:
            subprocess.CalledProcessError: If Gradle command fails.
        """
        try:
            # Use tasks --all to get all tasks including inherited ones
            # For root project (: or empty), use just "tasks", for subprojects use "project:tasks"
            is_root = project == ":" or project == "" or project is None
            task_cmd = "tasks" if is_root else f"{project}:tasks"
            result = subprocess.run(
                [str(self.wrapper_script), task_cmd, "--all"],
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                check=True,
            )

            tasks = []
            in_task_section = False
            current_group = None

            for line in result.stdout.split("\n"):
                line_stripped = line.strip()
                
                # Skip empty lines
                if not line_stripped:
                    continue
                
                # Look for task group headers (end with "tasks")
                if line_stripped.endswith(" tasks") and line_stripped[0].isupper():
                    in_task_section = True
                    current_group = line_stripped.replace(" tasks", "").strip()
                    continue
                
                # Skip separators and rules
                if line_stripped.startswith("-") or "Pattern:" in line_stripped:
                    continue
                
                # Stop at help text
                if "To see all tasks" in line_stripped or line_stripped.startswith("BUILD"):
                    break
                
                # Parse task lines when in a task section
                if in_task_section:
                    # Task lines format: "taskName - description"
                    task_match = re.match(r"^(\w+)\s+-\s+(.+)$", line_stripped)
                    if task_match:
                        task_name = task_match.group(1)
                        description = task_match.group(2)
                        
                        tasks.append(
                            GradleTask(
                                name=task_name,
                                project=project,
                                description=description,
                                group=current_group,
                            )
                        )
                    # Also handle tasks without description
                    elif re.match(r"^(\w+)$", line_stripped):
                        task_name = line_stripped
                        tasks.append(
                            GradleTask(
                                name=task_name,
                                project=project,
                                description="",
                                group=current_group,
                            )
                        )

            return tasks
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to list tasks for project {project}: {e.stderr}"
            ) from e

    async def run_task(self, task: str, args: Optional[list[str]] = None, ctx: Optional['Context'] = None) -> dict:
        """Run a Gradle task with real-time progress reporting.

        Args:
            task: Task name to run. Can be simple (e.g., 'build') for root project
                  or qualified with project path (e.g., ':app:build', ':core:test').
            args: Additional arguments to pass to Gradle.
            ctx: Optional FastMCP Context for progress reporting.

        Returns:
            Dictionary with 'success', 'error'
            - success (bool): True if task completed successfully
            - error (str or None): Error message if task failed, None otherwise

        Raises:
            ValueError: If task is a cleaning task.
        """
        if self._is_cleaning_task(task):
            raise ValueError(
                f"Task '{task}' is a cleaning task and cannot be run via run_task. "
                "Please use the clean tool instead."
            )

        # Validate arguments to prevent command injection
        if args:
            self._validate_gradle_args(args)

        # Remove -q flag to get progress output
        cmd = [str(self.wrapper_script), task, "--no-build-cache"]

        if args:
            cmd.extend(args)

        try:
            process = subprocess.Popen(
                cmd,
                cwd=str(self.project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            
            stdout_lines = []
            stderr_lines = []
            
            # Pattern to match Gradle progress: <============-> 93% EXECUTING [19s]
            progress_pattern = re.compile(r'(\d+)%')
            
            # Read output in real-time
            while True:
                # Check if process has finished
                if process.poll() is not None:
                    # Read any remaining output
                    remaining_out = process.stdout.read()
                    remaining_err = process.stderr.read()
                    if remaining_out:
                        stdout_lines.append(remaining_out)
                    if remaining_err:
                        stderr_lines.append(remaining_err)
                    break
                
                # Read available output
                out_line = process.stdout.readline()
                if out_line:
                    stdout_lines.append(out_line)
                    if ctx:
                        ctx.info(f"{out_line}")
                    
                    # Parse progress: look for patterns like "93% EXECUTING" or "<======> 93%"
                    if ctx and '%' in out_line:
                        match = progress_pattern.search(out_line)
                        if match:
                            progress = int(match.group(1))
                            await ctx.report_progress(progress=progress, total=100)
                
                err_line = process.stderr.readline()
                if err_line:
                    stderr_lines.append(err_line)
                
                # Small async sleep to not block event loop
                await asyncio.sleep(0.01)
            
            stdout = ''.join(stdout_lines)
            stderr = ''.join(stderr_lines)
            
            if process.returncode == 0:
                return {
                    "success": True,
                    "error": None
                }
            else:
                # Extract comprehensive error message using helper method
                error_message = self._extract_error_message(stdout, stderr, "Task failed")
                
                return {
                    "success": False,
                    "error": error_message
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    async def clean(self, project: Optional[str] = None, ctx: Optional['Context'] = None) -> dict:
        """Run the clean task for a project.

        Args:
            project: Project path (e.g., ':app'). Use ':' or empty string or None for root project.
            ctx: FastMCP context for progress reporting and logging.

        Returns:
            Dictionary with 'success', 'error', 'stdout', and 'stderr' keys.
            - success (bool): True if clean completed successfully
            - error (str or None): Error message if clean failed, None otherwise
            - stdout (str): Standard output from Gradle
            - stderr (str): Standard error from Gradle

        Raises:
            subprocess.CalledProcessError: If Gradle command fails.
        """
        # Root project if project is None, empty, or ":"
        is_root = project is None or project == "" or project == ":"
        project_arg = "" if is_root else f"{project}:"
        # Remove -q to get progress output
        cmd = [str(self.wrapper_script), f"{project_arg}clean", "--no-build-cache"]

        try:
            progress_pattern = re.compile(r'(\d+)%')
            
            process = subprocess.Popen(
                cmd,
                cwd=str(self.project_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            
            stdout_lines = []
            stderr_lines = []
            
            # Read output line by line in real-time
            while True:
                # Check if process has finished
                if process.poll() is not None:
                    # Read any remaining output
                    remaining_out = process.stdout.read()
                    remaining_err = process.stderr.read()
                    if remaining_out:
                        stdout_lines.append(remaining_out)
                    if remaining_err:
                        stderr_lines.append(remaining_err)
                    break
                
                # Read available output
                out_line = process.stdout.readline()
                if out_line:
                    stdout_lines.append(out_line)
                    
                    # Parse progress
                    if ctx and '%' in out_line:
                        match = progress_pattern.search(out_line)
                        if match:
                            progress = int(match.group(1))
                            await ctx.report_progress(progress=progress, total=100)
                
                err_line = process.stderr.readline()
                if err_line:
                    stderr_lines.append(err_line)
                
                # Small async sleep to not block event loop
                await asyncio.sleep(0.01)
            
            stdout = ''.join(stdout_lines)
            stderr = ''.join(stderr_lines)
            
            if process.returncode == 0:
                return {
                    "success": True,
                    "error": None
                }
            else:
                # Extract comprehensive error message using helper method
                error_message = self._extract_error_message(stdout, stderr, "Clean failed")
                
                return {
                    "success": False,
                    "error": error_message
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

