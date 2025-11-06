"""Security tests for Gradle MCP server."""

import pytest
from gradle_mcp.gradle import GradleWrapper


class TestArgumentValidation:
    """Test suite for Gradle argument validation security."""

    def test_safe_arguments_allowed(self):
        """Test that safe arguments from the allow-list are permitted."""
        wrapper = GradleWrapper.__new__(GradleWrapper)
        
        # Test various safe arguments
        safe_args_examples = [
            ['--info'],
            ['-i'],
            ['--debug', '--stacktrace'],
            ['-x', 'test'],
            ['--exclude-task', 'lint'],
            ['--parallel', '--max-workers', '4'],
            ['--max-workers=4'],
            ['--continue'],
            ['--dry-run'],
            ['--refresh-dependencies'],
            ['--no-build-cache'],
            ['--scan'],
        ]
        
        for args in safe_args_examples:
            # Should not raise any exception
            wrapper._validate_gradle_args(args)
    
    def test_dangerous_init_script_blocked(self):
        """Test that --init-script is blocked to prevent code execution."""
        wrapper = GradleWrapper.__new__(GradleWrapper)
        
        # Test various forms of --init-script
        dangerous_args = [
            ['--init-script', 'malicious.gradle'],
            ['--init-script=malicious.gradle'],
            ['-I', 'malicious.gradle'],
        ]
        
        for args in dangerous_args:
            with pytest.raises(ValueError, match="not allowed due to security concerns"):
                wrapper._validate_gradle_args(args)
    
    def test_dangerous_project_prop_blocked(self):
        """Test that -P/--project-prop is blocked."""
        wrapper = GradleWrapper.__new__(GradleWrapper)
        
        dangerous_args = [
            ['--project-prop', 'key=value'],
            ['--project-prop=key=value'],
            ['-P', 'key=value'],
            ['-Pkey=value'],
        ]
        
        for args in dangerous_args:
            with pytest.raises(ValueError, match="not allowed due to security concerns"):
                wrapper._validate_gradle_args(args)
    
    def test_dangerous_system_prop_blocked(self):
        """Test that -D is blocked."""
        wrapper = GradleWrapper.__new__(GradleWrapper)
        
        dangerous_args = [
            ['-D', 'prop=value'],
            ['-Dprop=value'],
            ['--system-prop', 'prop=value'],
        ]
        
        for args in dangerous_args:
            with pytest.raises(ValueError, match="not allowed due to security concerns"):
                wrapper._validate_gradle_args(args)
    
    def test_dangerous_settings_file_blocked(self):
        """Test that -c/--settings-file is blocked."""
        wrapper = GradleWrapper.__new__(GradleWrapper)
        
        dangerous_args = [
            ['--settings-file', 'malicious.gradle'],
            ['--settings-file=malicious.gradle'],
            ['-c', 'malicious.gradle'],
        ]
        
        for args in dangerous_args:
            with pytest.raises(ValueError, match="not allowed due to security concerns"):
                wrapper._validate_gradle_args(args)
    
    def test_dangerous_build_file_blocked(self):
        """Test that -b/--build-file is blocked."""
        wrapper = GradleWrapper.__new__(GradleWrapper)
        
        dangerous_args = [
            ['--build-file', 'malicious.gradle'],
            ['--build-file=malicious.gradle'],
            ['-b', 'malicious.gradle'],
        ]
        
        for args in dangerous_args:
            with pytest.raises(ValueError, match="not allowed due to security concerns"):
                wrapper._validate_gradle_args(args)
    
    def test_dangerous_gradle_user_home_blocked(self):
        """Test that -g/--gradle-user-home is blocked."""
        wrapper = GradleWrapper.__new__(GradleWrapper)
        
        dangerous_args = [
            ['--gradle-user-home', '/tmp/malicious'],
            ['--gradle-user-home=/tmp/malicious'],
            ['-g', '/tmp/malicious'],
        ]
        
        for args in dangerous_args:
            with pytest.raises(ValueError, match="not allowed due to security concerns"):
                wrapper._validate_gradle_args(args)
    
    def test_dangerous_project_dir_blocked(self):
        """Test that -p/--project-dir is blocked."""
        wrapper = GradleWrapper.__new__(GradleWrapper)
        
        dangerous_args = [
            ['--project-dir', '/tmp/malicious'],
            ['--project-dir=/tmp/malicious'],
            ['-p', '/tmp/malicious'],
        ]
        
        for args in dangerous_args:
            with pytest.raises(ValueError, match="not allowed due to security concerns"):
                wrapper._validate_gradle_args(args)
    
    def test_dangerous_include_build_blocked(self):
        """Test that --include-build is blocked."""
        wrapper = GradleWrapper.__new__(GradleWrapper)
        
        dangerous_args = [
            ['--include-build', '/tmp/malicious'],
            ['--include-build=/tmp/malicious'],
        ]
        
        for args in dangerous_args:
            with pytest.raises(ValueError, match="not allowed due to security concerns"):
                wrapper._validate_gradle_args(args)
    
    def test_unknown_arguments_blocked(self):
        """Test that unknown/unlisted arguments are blocked by default."""
        wrapper = GradleWrapper.__new__(GradleWrapper)
        
        unknown_args = [
            ['--some-unknown-flag'],
            ['--random-option=value'],
            ['-z'],
        ]
        
        for args in unknown_args:
            with pytest.raises(ValueError, match="not in the allow-list"):
                wrapper._validate_gradle_args(args)
    
    def test_empty_args_allowed(self):
        """Test that empty or None args are handled correctly."""
        wrapper = GradleWrapper.__new__(GradleWrapper)
        
        # Should not raise
        wrapper._validate_gradle_args(None)
        wrapper._validate_gradle_args([])
    
    def test_mixed_safe_arguments(self):
        """Test combination of safe arguments."""
        wrapper = GradleWrapper.__new__(GradleWrapper)
        
        # Complex but safe combination
        args = [
            '--info',
            '--parallel',
            '--max-workers', '8',
            '-x', 'test',
            '--exclude-task', 'lint',
            '--continue',
            '--stacktrace',
        ]
        
        # Should not raise
        wrapper._validate_gradle_args(args)
    
    def test_safe_arg_followed_by_dangerous_blocked(self):
        """Test that dangerous args are blocked even when mixed with safe ones."""
        wrapper = GradleWrapper.__new__(GradleWrapper)
        
        # Start with safe args, then add dangerous one
        args = ['--info', '--init-script', 'malicious.gradle']
        
        with pytest.raises(ValueError, match="not allowed due to security concerns"):
            wrapper._validate_gradle_args(args)


class TestCommandInjectionPrevention:
    """Test suite specifically for command injection attack prevention."""
    
    def test_rce_via_init_script_prevented(self):
        """Test that the original RCE vector via --init-script is blocked."""
        wrapper = GradleWrapper.__new__(GradleWrapper)
        
        # This was the original attack vector
        malicious_args = [
            '--init-script',
            '/tmp/malicious.gradle'  # Could contain arbitrary Groovy code
        ]
        
        with pytest.raises(ValueError, match="not allowed due to security concerns"):
            wrapper._validate_gradle_args(malicious_args)
    
    def test_rce_via_init_script_short_form_prevented(self):
        """Test that -I form is also blocked."""
        wrapper = GradleWrapper.__new__(GradleWrapper)
        
        malicious_args = ['-I', '/tmp/evil.gradle']
        
        with pytest.raises(ValueError, match="not allowed due to security concerns"):
            wrapper._validate_gradle_args(malicious_args)
    
    def test_property_injection_prevented(self):
        """Test that property injection attacks are prevented."""
        wrapper = GradleWrapper.__new__(GradleWrapper)
        
        # Attacker trying to inject properties
        malicious_args = ['-P', 'systemProp.java.home=/tmp/malicious']
        
        with pytest.raises(ValueError, match="not allowed due to security concerns"):
            wrapper._validate_gradle_args(malicious_args)
    
    def test_file_path_manipulation_prevented(self):
        """Test that file path manipulation is prevented."""
        wrapper = GradleWrapper.__new__(GradleWrapper)
        
        # Various ways to manipulate file paths
        attacks = [
            ['-b', '/etc/passwd'],
            ['-c', '/tmp/malicious.settings.gradle'],
            ['-g', '/tmp/malicious-gradle-home'],
            ['-p', '/tmp/other-project'],
        ]
        
        for attack in attacks:
            with pytest.raises(ValueError, match="not allowed due to security concerns"):
                wrapper._validate_gradle_args(attack)
