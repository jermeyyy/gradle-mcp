"""MCP Server for running Gradle tasks."""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP, Context
from pydantic import BaseModel

from gradle_mcp.gradle import GradleWrapper, GradleTask, GradleProject


# Initialize FastMCP server
mcp = FastMCP("gradle-mcp", "Gradle Model Context Protocol Server")


class TaskResult(BaseModel):
    """Result of running a Gradle task."""
    success: bool
    error: Optional[str] = None


class ProjectInfo(BaseModel):
    """Information about a Gradle project."""
    name: str
    path: str
    description: Optional[str] = None


class TaskInfo(BaseModel):
    """Information about a Gradle task."""
    name: str
    project: str
    description: Optional[str] = None
    group: Optional[str] = None


def _get_gradle_wrapper(ctx: Optional[Context] = None) -> GradleWrapper:
    """Get a GradleWrapper instance, optionally using context to determine project root.

    Respects the following environment variables:
    - GRADLE_PROJECT_ROOT: Root directory of Gradle project (default: current directory)
    - GRADLE_WRAPPER: Path to Gradle wrapper script (optional, auto-detected if not set)

    Args:
        ctx: MCP Context (optional).

    Returns:
        GradleWrapper instance.

    Raises:
        FileNotFoundError: If Gradle wrapper cannot be found.
    """
    project_root = os.getenv("GRADLE_PROJECT_ROOT") or os.getcwd()
    wrapper_path = os.getenv("GRADLE_WRAPPER")
    
    gradle = GradleWrapper(project_root)
    
    # If a custom wrapper path is specified, override the auto-detected one
    if wrapper_path:
        wrapper_path_obj = Path(wrapper_path)
        if not wrapper_path_obj.exists():
            raise FileNotFoundError(
                f"Gradle wrapper not found at specified path: {wrapper_path}. "
                "Please verify GRADLE_WRAPPER environment variable."
            )
        gradle.wrapper_script = wrapper_path_obj
    
    return gradle


@mcp.tool()
async def list_projects(ctx: Context) -> list[ProjectInfo]:
    """List all Gradle projects in the workspace.

    Returns:
        List of Gradle projects.
    """
    try:
        await ctx.info("Listing all Gradle projects")
        gradle = _get_gradle_wrapper(ctx)
        projects = gradle.list_projects()
        await ctx.info(f"Found {len(projects)} projects: {', '.join(p.name for p in projects)}")
        return [
            ProjectInfo(
                name=p.name,
                path=p.path,
                description=p.description,
            )
            for p in projects
        ]
    except Exception as e:
        raise ValueError(f"Failed to list projects: {str(e)}")


@mcp.tool()
async def list_project_tasks(project: Optional[str] = None, ctx: Context = None) -> list[TaskInfo]:
    """List all tasks available in a Gradle project.

    Args:
        project: Project path (e.g., ':app' or 'lib:module'). 
                Use None, empty string, or ':' for root project.
        ctx: MCP Context.

    Returns:
        List of available tasks in the project.
    """
    try:
        await ctx.info(f"Listing tasks for project: {project or 'root'}")
        gradle = _get_gradle_wrapper(ctx)
        # Normalize root project: None, empty, or ":" all mean root
        project_arg = project if project and project != "" else ":"
        tasks = gradle.list_tasks(project_arg)
        await ctx.info(f"Found {len(tasks)} tasks for project {project_arg}")
        return [
            TaskInfo(
                name=t.name,
                project=t.project,
                description=t.description,
                group=t.group,
            )
            for t in tasks
        ]
    except Exception as e:
        raise ValueError(f"Failed to list tasks: {str(e)}")


@mcp.tool()
async def run_task(
    task: str,
    args: Optional[list[str]] = None,
    ctx: Context = None,
) -> TaskResult:
    """Run a Gradle task.

    This tool cannot run cleaning tasks (clean, cleanBuild, etc.).
    Use the `clean` tool for cleaning tasks instead.

    Args:
        task: Task name to run. Can be simple (e.g., 'build', 'test') for root project
              or qualified with project path (e.g., ':app:build', ':core:test').
        args: Additional arguments to pass to Gradle (e.g., ['-x', 'test']).

    Returns:
        TaskResult with success status and error message if failed.

    Raises:
        ValueError: If the task is a cleaning task.
    """
    try:
        await ctx.info(f"Running task: {task}" + (f" with args: {args}" if args else ""))
        
        gradle = _get_gradle_wrapper(ctx)
        
        # run_task now handles progress reporting internally by parsing Gradle output
        result = await gradle.run_task(task, args, ctx)
        
        # Log Gradle output
        if result.get("stdout"):
            await ctx.debug(f"Gradle stdout:\n{result['stdout']}")
        if result.get("stderr"):
            await ctx.debug(f"Gradle stderr:\n{result['stderr']}")
        
        if result["success"]:
            await ctx.info(f"Task {task} completed successfully")
        else:
            await ctx.error(f"Task {task} failed", extra={"error": result.get('error')})
        
        return TaskResult(
            success=result["success"],
            error=result.get("error"),
        )
    except ValueError as e:
        # Task is a cleaning task
        raise ValueError(str(e))
    except Exception as e:
        # Report error progress
        await ctx.report_progress(progress=100, total=100)
        return TaskResult(
            success=False,
            error=str(e),
        )


@mcp.tool()
async def clean(
    project: Optional[str] = None,
    ctx: Context = None,
) -> TaskResult:
    """Clean build artifacts for a Gradle project.

    This is the only tool that should be used for cleaning tasks.

    Args:
        project: Project path (e.g., ':app'). 
                Use None, empty string, or ':' for root project.

    Returns:
        TaskResult with success status and error message if failed.
    """
    try:
        await ctx.info(f"Cleaning project: {project or 'root'}")
        
        gradle = _get_gradle_wrapper(ctx)
        
        # clean now handles progress reporting internally by parsing Gradle output
        result = await gradle.clean(project, ctx)
        
        # Log Gradle output
        if result.get("stdout"):
            await ctx.debug(f"Gradle stdout:\n{result['stdout']}")
        if result.get("stderr"):
            await ctx.debug(f"Gradle stderr:\n{result['stderr']}")
        
        if result["success"]:
            await ctx.info(f"Clean completed successfully for project {project or 'root'}")
        else:
            await ctx.error(f"Clean failed for project {project or 'root'}", extra={"error": result.get('error')})
        
        return TaskResult(
            success=result["success"],
            error=result.get("error"),
        )
    except Exception as e:
        return TaskResult(
            success=False,
            error=str(e),
        )


def main() -> None:
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
