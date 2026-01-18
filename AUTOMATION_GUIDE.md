# Documentation Automation Guide

## Overview

The documentation index is now **fully automated**. The system automatically generates and updates `DOCUMENTATION_INDEX.md` whenever documentation files change.

## Automation Features

### 1. **Manual Script** (Local)
Run anytime to regenerate the index:
```bash
python update_docs_index.py
```

**What it does:**
- Scans all markdown files in the project
- Counts lines and estimates pages
- Extracts topics and headers
- Generates fresh DOCUMENTATION_INDEX.md
- Reports statistics

### 2. **GitHub Actions** (Automatic)
Automatically runs when:
- Documentation files are pushed to main branch
- Pull requests modify .md files
- Workflow file is modified

**What it does:**
- Triggers automatically on commit
- Runs Python script
- Commits updated index if changed
- Pushes changes back to repository

## Setup Instructions

### Local Automation (Already Configured)
```bash
# Just run the script whenever you add documentation
python update_docs_index.py

# Or add it to your pre-commit hooks:
# 1. Create .git/hooks/pre-commit
# 2. Add: python update_docs_index.py
# 3. Make executable: chmod +x .git/hooks/pre-commit
```

### GitHub Actions (Already Configured)
The workflow file `.github/workflows/update-docs.yml` is already set up and will:
1. Trigger on any .md file change to main branch
2. Automatically regenerate DOCUMENTATION_INDEX.md
3. Commit and push updates if changes are detected
4. Run on pull requests to preview changes

**No additional setup required!** ✅

## How It Works

### Python Script: `update_docs_index.py`

```
Input: Documentation files (.md)
       ↓
    Analysis:
       - Count lines
       - Extract topics
       - Calculate pages
       ↓
    Generation:
       - Create table of contents
       - Build statistics
       - Format index
       ↓
Output: DOCUMENTATION_INDEX.md
```

### Workflow: `.github/workflows/update-docs.yml`

```
Git Push Event
       ↓
Trigger (if .md files changed)
       ↓
Checkout code
       ↓
Run Python 3.12
       ↓
Execute update_docs_index.py
       ↓
Check for changes
       ↓
Commit & Push (if changed)
       ↓
Done!
```

## Configuration

### Adding New Documentation Files

1. **Create your .md file** in the project root
2. **Run the script**:
   ```bash
   python update_docs_index.py
   ```
3. **Or just push** - GitHub Actions will run automatically

### Customizing the Script

Edit `update_docs_index.py` to:
- Add/remove files from `DOC_FILES` dict
- Change page calculation (currently 50 lines per page)
- Modify categories
- Adjust topic extraction logic

```python
DOC_FILES = {
    'YOUR_FILE.md': {
        'category': 'Category Name',
        'priority': 1,
        'description': 'Short description'
    },
}
```

## Automation Scripts

### Pre-commit Hook (Optional)
```bash
#!/bin/bash
# .git/hooks/pre-commit

echo "🔄 Updating documentation index..."
python update_docs_index.py

if [ $? -ne 0 ]; then
    echo "❌ Documentation update failed"
    exit 1
fi

git add DOCUMENTATION_INDEX.md
echo "✅ Documentation index updated"
```

### Manual Trigger Script
```bash
#!/bin/bash
# scripts/update-docs.sh

cd "$(dirname "$0")/.."
python update_docs_index.py
git add DOCUMENTATION_INDEX.md
git commit -m "docs: update DOCUMENTATION_INDEX.md"
git push origin main
```

## Features of the Automation

### ✅ Smart Detection
- Only commits if index actually changed
- Detects new and modified files
- Extracts meaningful statistics

### ✅ Comprehensive Statistics
- Line counting
- Page estimation
- Topic extraction
- Document categorization

### ✅ Formatting
- Markdown tables with stats
- Organized by category
- Priority-based ordering
- Readable output

### ✅ Cross-Platform
- Works on Windows, macOS, Linux
- Handles UTF-8 encoding
- Error handling for missing files

## Integration Points

### With Deployment
```bash
# Pre-deployment
python update_docs_index.py
git add .
git commit -m "docs: final index update"
git push origin main
```

### With CI/CD Pipeline
The GitHub Actions workflow integrates with:
- ✅ Pull Request checks
- ✅ Branch protection rules
- ✅ Automatic commits
- ✅ Status checks

### With Git Workflows
- **Feature branch**: Run script, commit, push
- **Pull request**: Workflow auto-updates index
- **Main branch**: Auto-committed on merge

## Maintenance

### Updating Statistics
The script automatically maintains:
- ✅ Line counts (real-time)
- ✅ Page estimates (auto-calculated)
- ✅ Topic extraction (from headings)
- ✅ File modification dates

### Adding New Documents
1. Create `YOUR_FILE.md`
2. Add to `DOC_FILES` dict in script
3. Run `python update_docs_index.py`
4. Commit changes

### Debugging

If index doesn't update:
```bash
# Check file exists
ls DOCUMENTATION_INDEX.md

# Run script with output
python update_docs_index.py

# Check git status
git status

# Verify changes
git diff DOCUMENTATION_INDEX.md
```

## Usage Examples

### Scenario 1: Adding New Documentation
```bash
# 1. Create new doc
echo "# New Feature" > NEW_FEATURE.md

# 2. Update index
python update_docs_index.py

# 3. Commit
git add .
git commit -m "docs: add new feature documentation"
```

### Scenario 2: Automatic GitHub Update
```bash
# Just push to main
git add NEW_FEATURE.md
git commit -m "Add new feature docs"
git push origin main

# ✅ GitHub Actions automatically:
#    - Generates index
#    - Commits update
#    - Pushes back
```

### Scenario 3: Pre-deployment Check
```bash
# Run before deployment
python update_docs_index.py

# Verify all docs are in index
grep "DEPLOYMENT_GUIDE.md" DOCUMENTATION_INDEX.md

# Deploy with confidence
git push origin main
```

## Performance

- **Script execution**: < 1 second
- **GitHub Actions run**: < 30 seconds
- **File scanning**: All docs (7-10 files)
- **Index generation**: Automatic

## Troubleshooting

### Index not updating locally
```bash
# Force regeneration
rm DOCUMENTATION_INDEX.md
python update_docs_index.py
```

### GitHub Actions not triggering
```
Check:
1. Workflow file in .github/workflows/
2. Branch is 'main'
3. File changes are .md files
4. Workflow is enabled in GitHub
```

### Encoding issues
```python
# Script handles UTF-8 automatically
# For custom encoding:
open(filepath, 'r', encoding='utf-8', errors='ignore')
```

## Files Involved

```
project/
├── update_docs_index.py          # Main automation script
├── DOCUMENTATION_INDEX.md        # Auto-generated (DO NOT EDIT)
├── .github/
│   └── workflows/
│       └── update-docs.yml       # GitHub Actions workflow
└── *.md files                    # Documentation files (source)
```

## Best Practices

1. **Always run script locally** before pushing
   ```bash
   python update_docs_index.py
   ```

2. **Don't manually edit DOCUMENTATION_INDEX.md** - it's generated
   - Let the automation handle it
   - Changes will be overwritten

3. **Add meaningful documentation**
   - Use proper headings (### for topics)
   - Keep files organized
   - Include descriptions

4. **Run before deployment**
   ```bash
   python update_docs_index.py
   git push origin main
   ```

5. **Monitor GitHub Actions**
   - Check workflow runs
   - Verify auto-commits
   - Review any errors

## Advanced Usage

### Custom Script Extensions
```python
# Add to update_docs_index.py

def generate_table_of_contents():
    """Generate TOC from files"""
    # Your custom logic
    pass

def validate_documentation():
    """Validate doc structure"""
    # Your custom logic
    pass
```

### Integration with Other Tools
```bash
# With pre-commit framework
- repo: local
  hooks:
    - id: update-docs
      name: Update Documentation Index
      entry: python update_docs_index.py
      language: system
      files: '\.md$'
      stages: [commit]
```

## Summary

✅ **Automation enabled**
- Python script for manual runs
- GitHub Actions for automatic updates
- No manual editing required
- Always up-to-date statistics

🚀 **Next Steps:**
1. Push documentation changes
2. GitHub Actions auto-updates index
3. Or run `python update_docs_index.py` locally
4. Enjoy automatic documentation management!

---

**Configuration**: Complete ✅  
**Status**: Fully Automated ✅  
**Ready to Use**: Yes ✅
