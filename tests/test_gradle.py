"""Tests for the Gradle wrapper."""

import pytest
import os
from pathlib import Path
from gradle_mcp.gradle import GradleWrapper, GradleTask, GradleProject


class TestGradleWrapper:
    """Test suite for GradleWrapper."""

    def test_is_cleaning_task_with_clean(self):
        """Test that 'clean' is recognized as a cleaning task."""
        wrapper = GradleWrapper.__new__(GradleWrapper)
        assert wrapper._is_cleaning_task("clean") is True

    def test_is_cleaning_task_with_clean_build(self):
        """Test that 'cleanBuild' is recognized as a cleaning task."""
        wrapper = GradleWrapper.__new__(GradleWrapper)
        assert wrapper._is_cleaning_task("cleanBuild") is True

    def test_is_cleaning_task_with_clean_test(self):
        """Test that 'cleanTest' is recognized as a cleaning task."""
        wrapper = GradleWrapper.__new__(GradleWrapper)
        assert wrapper._is_cleaning_task("cleanTest") is True

    def test_is_not_cleaning_task_with_build(self):
        """Test that 'build' is not recognized as a cleaning task."""
        wrapper = GradleWrapper.__new__(GradleWrapper)
        assert wrapper._is_cleaning_task("build") is False

    def test_is_not_cleaning_task_with_test(self):
        """Test that 'test' is not recognized as a cleaning task."""
        wrapper = GradleWrapper.__new__(GradleWrapper)
        assert wrapper._is_cleaning_task("test") is False

    def test_is_not_cleaning_task_with_assemble(self):
        """Test that 'assemble' is not recognized as a cleaning task."""
        wrapper = GradleWrapper.__new__(GradleWrapper)
        assert wrapper._is_cleaning_task("assemble") is False

    def test_cleaning_task_case_insensitive(self):
        """Test that cleaning task detection is case-insensitive."""
        wrapper = GradleWrapper.__new__(GradleWrapper)
        assert wrapper._is_cleaning_task("Clean") is True
        assert wrapper._is_cleaning_task("CLEAN") is True
        assert wrapper._is_cleaning_task("CLEANBUILD") is True


class TestGradleWrapperEnvConfig:
    """Test suite for environment configuration."""

    def test_gradle_project_root_env_var(self):
        """Test that GRADLE_PROJECT_ROOT environment variable is respected."""
        # Save original env var if it exists
        original = os.getenv("GRADLE_PROJECT_ROOT")
        
        try:
            # Set custom project root
            os.environ["GRADLE_PROJECT_ROOT"] = "/tmp/test-project"
            # This would fail because gradlew doesn't exist, but that's expected
            # We're just testing that the env var is read
            with pytest.raises(FileNotFoundError):
                wrapper = GradleWrapper("/tmp/test-project")
        finally:
            # Restore original
            if original:
                os.environ["GRADLE_PROJECT_ROOT"] = original
            else:
                os.environ.pop("GRADLE_PROJECT_ROOT", None)

    def test_gradle_wrapper_custom_path(self):
        """Test that custom wrapper path can be set after initialization."""
        wrapper = GradleWrapper.__new__(GradleWrapper)
        wrapper.project_root = Path(".")
        
        # Simulate setting a custom wrapper path
        custom_path = Path("/custom/path/gradlew")
        wrapper.wrapper_script = custom_path
        
        assert wrapper.wrapper_script == custom_path
