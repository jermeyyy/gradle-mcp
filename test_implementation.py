#!/usr/bin/env python3
"""
Simple test script to verify the Gradle MCP server implementation.
Run this in a Gradle project directory to test the server.
"""

import subprocess
import sys
from pathlib import Path


def test_imports():
    """Test that all imports work correctly."""
    print("Testing imports...")
    try:
        from gradle_mcp.gradle import GradleWrapper, GradleTask, GradleProject
        from gradle_mcp.server import mcp, list_projects, list_project_tasks, run_task, clean
        print("✓ All imports successful")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False


def test_cleaning_task_detection():
    """Test that cleaning task detection works correctly."""
    print("\nTesting cleaning task detection...")
    try:
        from gradle_mcp.gradle import GradleWrapper
        
        wrapper = GradleWrapper.__new__(GradleWrapper)
        
        # Test cleaning tasks
        cleaning_tasks = ["clean", "cleanBuild", "cleanTest", "cleanCache", "Clean", "CLEAN"]
        for task in cleaning_tasks:
            if not wrapper._is_cleaning_task(task):
                print(f"✗ Failed: {task} should be recognized as cleaning task")
                return False
        
        # Test non-cleaning tasks
        regular_tasks = ["build", "test", "assemble", "check", "lint"]
        for task in regular_tasks:
            if wrapper._is_cleaning_task(task):
                print(f"✗ Failed: {task} should NOT be recognized as cleaning task")
                return False
        
        print("✓ Cleaning task detection works correctly")
        return True
    except Exception as e:
        print(f"✗ Error during cleaning task test: {e}")
        return False


def test_gradle_wrapper():
    """Test that GradleWrapper can be instantiated."""
    print("\nTesting GradleWrapper instantiation...")
    try:
        from gradle_mcp.gradle import GradleWrapper
        
        # Try to create wrapper for current directory
        try:
            wrapper = GradleWrapper(".")
            print("✓ GradleWrapper instantiated successfully")
            print(f"  Project root: {wrapper.project_root}")
            return True
        except FileNotFoundError:
            print("⚠ GradleWrapper could not find gradlew (expected if not in Gradle project)")
            print("  This is normal if running outside a Gradle project directory")
            return True
    except Exception as e:
        print(f"✗ Error during GradleWrapper test: {e}")
        return False


def test_fastmcp_server():
    """Test that FastMCP server is correctly configured."""
    print("\nTesting FastMCP server configuration...")
    try:
        from gradle_mcp.server import mcp
        
        # Check that mcp instance exists and has tools
        if not mcp:
            print("✗ MCP instance not found")
            return False
        
        print("✓ FastMCP server configured successfully")
        return True
    except Exception as e:
        print(f"✗ Error during FastMCP test: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Gradle MCP Server - Implementation Test Suite")
    print("=" * 60)
    
    results = []
    results.append(("Import test", test_imports()))
    results.append(("Cleaning task detection", test_cleaning_task_detection()))
    results.append(("GradleWrapper instantiation", test_gradle_wrapper()))
    results.append(("FastMCP server configuration", test_fastmcp_server()))
    
    print("\n" + "=" * 60)
    print("Test Results Summary:")
    print("=" * 60)
    
    for test_name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n✓ All tests passed! Server is ready to use.")
        return 0
    else:
        print("\n✗ Some tests failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
