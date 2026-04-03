# Repository Update Documentation Tool

A workflow automation tool for generating copyright registration documentation from git repository changes. This tool helps legal teams track and document new authorship in source code repositories for US Copyright Office submissions.

## Purpose

When registering source code with the US Copyright Office, attorneys must periodically submit documentation showing updates to the registered work. This tool automates the process of:

1. **Tracking changes** between copyright registration submissions
2. **Filtering out deletions** (only new authorship matters for copyright)
3. **Generating clean diffs** showing only additions to the codebase
4. **Creating submission packages** with PDFs and archives ready for filing

### Why Filter Out Deletions?

Copyright registration focuses on **new creative work**. When updating a registration:
- ✅ **Additions** represent new authorship that should be documented
- ❌ **Deletions** don't represent new creative work and are not relevant
- ✅ **File headers** and context are kept for clarity

## Features

### Core Functionality

- **Multi-repository support**: Track multiple repositories in a single workflow
- **Commit range specifications**: Define exactly which changes to include (starting_commit → ending_commit)
- **Duplicate repository support**: Same repo can appear multiple times with different commit ranges
- **Deletion filtering**: Automatically removes deleted lines from diffs while preserving additions
- **Multiple output formats**: Generates .diff files, combined .txt, .pdf, and .zip archives

### Smart Diff Processing

The tool intelligently processes git diffs:
- Keeps all added lines (prefixed with `+`)
- Removes deleted lines (prefixed with `-`)
- Preserves file headers (`---` and `+++`)
- Maintains context lines (no prefix)
- Handles edge cases like markdown `---` separators and YAML frontmatter

### Build Management

All temporary files are organized in a single `build/` directory:
```
build/
├── repos/          # Cloned repositories
├── diffs/          # Generated .diff files
│   └── README.txt  # Metadata about diffs
├── runlog.txt      # Combined diff content
├── runlog.pdf      # PDF version (requires cupsfilter)
└── runlog.zip      # Archive of all diffs
```

## Installation

### Prerequisites

- Python 3.7+
- Git
- `cupsfilter` (optional, for PDF generation)

### Setup

1. Clone the repository:
```bash
git clone git@github.com:lucasgonze/repo-update-documentation.git
cd repo-update-documentation
```

2. Create and activate virtual environment:
```bash
python3 -m venv myenv
source myenv/bin/activate
```

3. Install dependencies (if any are added):
```bash
pip install -r requirements.txt  # Currently no external dependencies
```

## Configuration

Edit `repos-config.json` to specify repositories and commit ranges:

```json
{
  "version": "2.0",
  "repos_dir": "repos",
  "output_dir": "diffs",
  "repositories": [
    {
      "name": "my-project",
      "url": "git@github.com:org/my-project.git",
      "starting_commit": "abc1234",
      "ending_commit": "def5678",
      "description": "Q1 2024 updates"
    },
    {
      "name": "my-project",
      "url": "git@github.com:org/my-project.git",
      "starting_commit": "def5678",
      "ending_commit": "HEAD",
      "description": "Q2 2024 updates"
    }
  ]
}
```

### Configuration Fields

- **name**: Repository name (used for directory naming)
- **url**: Git repository URL (SSH or HTTPS)
- **starting_commit**: Starting commit hash or reference
- **ending_commit**: Ending commit hash or reference (defaults to `HEAD` if omitted)
- **description**: Optional description for documentation purposes

## Usage

### Command Line Interface

The tool provides three main scripts in the `bin/` directory:

#### Run the Workflow

```bash
./bin/run <mode>
```

**Modes:**
- `full` - Complete workflow: sync repos, generate diffs, create archives (default)
- `check` - Only sync/update repositories
- `diff` - Generate diffs and archives (assumes repos are already synced)

**Examples:**
```bash
# Run complete workflow
./bin/run full

# Just update repositories
./bin/run check

# Generate diffs from already-cloned repos
./bin/run diff
```

#### Run Tests

```bash
./bin/test [-v]
```

Run the unit test suite. Use `-v` for verbose output.

**Example:**
```bash
# Run all tests
./bin/test

# Run with verbose output
./bin/test -v
```

#### Check Test Coverage

```bash
./bin/coverage
```

Generates test coverage report and HTML coverage visualization.

**Output:**
- Console report showing coverage percentages
- HTML report at `src/htmlcov/index.html`

### Direct Python Usage

You can also run the workflow directly:

```bash
python3 src/copyright_workflow.py <mode>
```

## Output

### Console Output

The workflow provides color-coded console output:

- **Info** (white): General progress messages
- **Success** (green): Successful operations
- **Warning** (yellow): Non-fatal issues (e.g., no changes found)
- **Error** (red): Fatal errors that prevent processing

**Example:**
```
Using build directory: /path/to/build
=== Syncing Repositories ===
Cloning my-project...

=== Generating Diffs ===
SUCCESS: Generated diff for my-project (abc1234..def5678)
WARNING: No new authorship found for other-project (xyz9999..HEAD)

=== Creating Archive ===
SUCCESS: Generated runlog.pdf
SUCCESS: Generated runlog.zip

=== Summary ===
SUCCESS: Workflow completed successfully!
```

### Generated Files

After running, check the `build/` directory:

1. **Individual diff files**: `build/diffs/*.diff` - One per repository entry
2. **README**: `build/diffs/README.txt` - Metadata about all diffs
3. **Combined diff**: `build/runlog.txt` - All diffs in one text file
4. **PDF**: `build/runlog.pdf` - PDF version of combined diff
5. **Archive**: `build/runlog.zip` - Zip file of all diffs

### Diff File Naming

- First entry for a repo: `repo-name.diff`
- Subsequent entries: `repo-name_2.diff`, `repo-name_3.diff`, etc.

## Test Data

The repository includes test data demonstrating all diff filtering features:

1. **Pure additions**: New file with only added lines
2. **Mixed changes**: Additions and deletions (deletions filtered out)
3. **Multiple files**: Several files changed in one commit
4. **Edge cases**: Files containing `---` in content (markdown, YAML)
5. **Only deletions**: Changes that result in empty filtered diff

Run `./bin/run full` to see these tests in action.

## Development

### Project Structure

```
repo-update-documentation/
├── bin/                    # Executable scripts
│   ├── run                # Run the workflow
│   ├── test               # Run tests
│   └── coverage           # Generate coverage report
├── src/                   # Source code
│   ├── copyright_workflow.py    # Main workflow implementation
│   └── test_copyright_workflow.py # Unit tests
├── test-data/             # Test data files
├── build/                 # Generated files (gitignored)
├── repos-config.json      # Repository configuration
└── README.md             # This file
```

### Running Tests

The test suite achieves 100% code coverage:

```bash
./bin/test -v              # Run tests with verbose output
./bin/coverage             # Check coverage
```

### Adding New Repositories

1. Edit `repos-config.json`
2. Add a new entry to the `repositories` array
3. Specify starting and ending commits
4. Run `./bin/run full`

## Troubleshooting

### Common Issues

**"Repository path does not exist"**
- Run with `check` mode first to clone repos: `./bin/run check`

**"Failed to resolve commit"**
- Ensure commit hashes exist in the repository
- Try using full commit hashes instead of short ones
- Make sure you've pushed commits to the remote

**"No new authorship found"**
- This is a warning, not an error
- Indicates the commit range only contained deletions
- The diff file will contain only file headers

**PDF generation fails or is incomplete**
- **Known Issue**: cupsfilter may truncate large files (>500KB), showing only the last diff
- **Workaround**: Use `runlog.txt` instead of the PDF - it contains all diffs correctly
- **Alternative**: Convert the .txt to PDF using other tools:
  - `enscript -p - runlog.txt | ps2pdf - runlog.pdf` (if available)
  - Use a text editor to print to PDF
  - Upload `runlog.txt` directly for copyright submissions
- The tool will still generate complete .txt and .zip files regardless
- Install cupsfilter: `brew install cups` (macOS) or `apt-get install cups` (Linux)

### Debug Mode

For detailed git output, check the console for error messages. All git operations show stderr output when they fail.

## License

Apache License 2.0 - See LICENSE file for details

## Contributing

This tool was developed for internal use at New Relic. Contributions are welcome:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass: `./bin/test`
5. Submit a pull request

## Support

For issues or questions:
- Create an issue in the GitHub repository
- Include the console output and `build/diffs/README.txt` content
- Specify your OS and Python version
