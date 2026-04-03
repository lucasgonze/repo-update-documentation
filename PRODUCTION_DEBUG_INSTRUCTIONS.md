# Instructions for Debugging on Production System

## Problem
Only the last diff appears in the output (runlog.txt, PDF, or zip).

## Solution: Run Debug Version

### Step 1: Pull Latest Code
```bash
cd /path/to/repo-update-documentation
git pull origin main
```

### Step 2: Clean and Run Debug Version
```bash
rm -rf build
./bin/run-debug full > debug_output.log 2>&1
```

Or if you can't use the bin script:
```bash
rm -rf build
python3 src/copyright_workflow_debug.py full > debug_output.log 2>&1
```

### Step 3: Verify the Issue
```bash
# Check how many diffs were generated
ls -lah build/diffs/*.diff | wc -l

# Check how many FILE: markers are in runlog.txt (should match number of diffs)
grep -c "^FILE:" build/runlog.txt

# Check size of combined file
wc -l build/runlog.txt
```

### Step 4: Collect Diagnostic Information

Run these commands and save the output:

```bash
# Show debug log
cat debug_output.log

# Show all diff files and sizes
ls -lah build/diffs/

# Show first 50 lines of combined output
head -50 build/runlog.txt

# Show last 50 lines of combined output
tail -50 build/runlog.txt

# Show all FILE: markers
grep "^FILE:" build/runlog.txt

# Show config
cat repos-config.json
```

### Step 5: Look for These Key Debug Messages

In `debug_output.log`, find these critical lines:

1. **Number of diff files found:**
   ```
   [DEBUG] Found X diff files:
   ```
   Should be 5 (or match number of entries in config)

2. **Each diff being processed:**
   ```
   [DEBUG] Processing diff file 1: repo-update-documentation.diff
   [DEBUG] Processing diff file 2: repo-update-documentation_2.diff
   ...
   ```
   Should see one for each diff file

3. **Final combined file stats:**
   ```
   [DEBUG] Combined file stats: X lines, Y bytes
   [DEBUG] Found X FILE: markers in combined output
   ```
   FILE: markers should equal number of diff files

4. **File write confirmations:**
   ```
   [DEBUG]   Wrote diff content for <filename>
   [DEBUG]   Flushed output buffer
   ```
   Should see these for each diff file

### What to Look For

**If bug is reproduced:**
- Debug log will show which step is failing
- You'll see where the process stops including all diffs
- File sizes and line counts will show truncation point

**Expected behavior (no bug):**
- All 5 diff files found and processed
- 5 FILE: markers in combined output
- Combined file has 160+ lines
- Each "Wrote diff content" message appears

### Common Scenarios

**Scenario 1: Fewer files found than expected**
```
[DEBUG] Found 2 diff files:
```
Problem: Not all diffs are being generated. Check earlier ERROR messages.

**Scenario 2: Files found but not all processed**
```
[DEBUG] Found 5 diff files:
[DEBUG] Processing diff file 1: repo-update-documentation.diff
[DEBUG]   Wrote diff content for repo-update-documentation.diff
# No more "Processing diff file" messages
```
Problem: Loop is breaking early. File glob might be returning files in unexpected order.

**Scenario 3: All files processed but output is truncated**
```
[DEBUG] Processing diff file 1: ...
[DEBUG] Processing diff file 2: ...
...
[DEBUG] Combined file stats: 50 lines, 1000 bytes
[DEBUG] Found 1 FILE: markers in combined output
```
Problem: File is being overwritten instead of appended, or buffer not flushing.

## Sending Results Back

Copy the entire `debug_output.log` file and share it along with:
1. Output of `ls -lah build/diffs/`
2. Output of `grep "^FILE:" build/runlog.txt`
3. First and last 50 lines of `build/runlog.txt`
4. Your `repos-config.json` file

This will help diagnose the exact issue.
