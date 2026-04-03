# Debugging Guide

## Debug Mode

If you're experiencing issues with the workflow (e.g., "only the last diff appears in output"), use the debug version to diagnose the problem.

### Running in Debug Mode

```bash
# Clean build directory and run with debug logging
rm -rf build
./bin/run-debug full
```

Or directly:
```bash
python3 src/copyright_workflow_debug.py full
```

### What Debug Mode Shows

The debug version adds detailed logging throughout the workflow:

#### During Diff Generation:
- Which repository is being processed
- Output file paths
- Number of filtered lines
- File write confirmations

#### During Archive Creation:
- List of all diff files found with sizes
- README.txt processing details
- Each diff file being added to runlog.txt
- Line counts and byte sizes at each step
- First/last lines of the combined output
- Count of FILE: markers (should equal number of diffs)
- PDF and ZIP generation details

### Key Debug Markers to Look For

1. **"Found X diff files:"** - Should match the number of repository entries in config
2. **"FILE: markers in combined output"** - Should equal the number of diff files
3. **"Combined file stats: X lines, Y bytes"** - Shows final combined file size
4. **File content samples** - First 100 chars of each diff being written

### Example Debug Output

```
[DEBUG] Output directory: build/diffs
[DEBUG] Combined path: build/runlog.txt
[DEBUG] Found 5 diff files:
[DEBUG]   - repo-update-documentation.diff (482 bytes)
[DEBUG]   - repo-update-documentation_2.diff (377 bytes)
[DEBUG]   - repo-update-documentation_3.diff (1256 bytes)
[DEBUG]   - repo-update-documentation_4.diff (567 bytes)
[DEBUG]   - repo-update-documentation_5.diff (192 bytes)
[DEBUG] Writing README.txt (11 lines)...
[DEBUG] Processing diff file 1: repo-update-documentation.diff
[DEBUG]   Writing header: '\n================================================================================\nFILE: repo-update-documentation.diff\n================================================================================\n'
[DEBUG]   Reading 10 lines from repo-update-documentation.diff
[DEBUG]   Wrote diff content for repo-update-documentation.diff
[DEBUG]   Flushed output buffer
[DEBUG] Processing diff file 2: repo-update-documentation_2.diff
...
[DEBUG] Combined file stats: 161 lines, 4856 bytes
[DEBUG] Found 5 FILE: markers in combined output
```

### Common Issues and What to Look For

#### Issue: Only last diff appears in output

**Check these debug lines:**
1. How many diff files are found? `Found X diff files:`
2. Are all files being processed? Look for `Processing diff file X:` for each one
3. How many FILE: markers are in output? Should equal number of diff files
4. Check file sizes - are they all non-zero?

**Possible causes:**
- Output file being truncated (check file sizes)
- Loop not iterating over all files (check "Processing diff file" count)
- File writing failing silently (check "Wrote diff content" confirmations)
- Glob pattern not finding all files (check "Found X diff files" matches expected)

#### Issue: Missing diffs

**Check:**
1. Were all diffs generated? Look for `SUCCESS: Generated diff for...` messages
2. Are there errors during diff generation? Look for `ERROR:` or `WARNING:` messages
3. Check the README.txt content - does it list all expected repositories?

### Reporting the Issue

When reporting a bug, include:

1. **Full debug output**: `./bin/run-debug full > debug.log 2>&1`
2. **Config file**: Contents of `repos-config.json`
3. **File listing**: `ls -lah build/diffs/`
4. **File counts**:
   - `ls build/diffs/*.diff | wc -l`
   - `grep -c "^FILE:" build/runlog.txt`
5. **Sample of runlog.txt**:
   - `head -50 build/runlog.txt`
   - `tail -50 build/runlog.txt`

### Disabling Debug Mode

To turn off verbose logging, edit `src/copyright_workflow_debug.py` and set:

```python
DEBUG = False
```

at the top of the file (line 9).
