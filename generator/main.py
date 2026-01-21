import argparse
import os
import json
from generator.scanner import Scanner
try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = lambda: None
    
import hashlib


#TODO : add docstring to generate_issue_files


def generate_issue_files(report, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    
    # Process TODOs
    for item in report['todos']:
        title = f"TODO: {item['content'][:50]}..."
        body = f"""
# {title}

**File**: `{item['file']}:{item['line']}`
**Difficulty**: {item['difficulty']}

## Description
Found a TODO comment which might need addressing:
```python
{item['content']}
```

## detailed context
This TODO was identifying during an automated scan of the codebase.
"""
        _write_issue(output_dir, 'todo', item, title, body)

    # Process Missing Tests
    for item in report['missing_tests']:
        title = f"Missing Tests: {os.path.basename(item['file'])}"
        body = f"""
# {title}

**File**: `{item['file']}`
**Difficulty**: {item['difficulty']}

## Description
The file `{item['file']}` appears to be missing a corresponding test file.
Adding unit tests helps ensure code stability and reliability.

## Why this is good for beginners
{"This file is relatively small, making it a great starting point for writing your first unit test." if item['difficulty'] == 'Easy' else "Writing tests is a great way to learn the codebase."}
"""
        _write_issue(output_dir, 'test', item, title, body)

    # Process Complexity
    for item in report['complex_files']:
        title = f"Refactor: {os.path.basename(item['file'])} is too complex"
        body = f"""
# {title}

**File**: `{item['file']}`
**Difficulty**: {item['difficulty']}

## Description
This file has {item['lines']} lines, which exceeds the recommended limit.
Consider breaking it down into smaller modules or functions.
"""
        _write_issue(output_dir, 'complexity', item, title, body)

    # Process Undocumented Functions
    for item in report['undocumented_functions']:
        title = f"Docs: Add docstring to {item['function']}"
        body = f"""
# {title}

**File**: `{item['file']}:{item['line']}`
**Difficulty**: {item['difficulty']}

## Description
The function `{item['function']}` is missing a docstring.
Good documentation is essential for maintainability.

## Why this is good for beginners
Writing documentation is an excellent way to learn what a function does without risking breaking changes.
"""
        _write_issue(output_dir, 'doc', item, title, body)

        _write_issue(output_dir, 'doc', item, title, body)

    # Process Security Issues
    for item in report.get('security_issues', []):
        title = f"Security: {item['issue']}"
        body = f"""
# {title}

**File**: `{item['file']}`
**Difficulty**: {item['difficulty']}
**Pattern**: `{item.get('pattern', 'N/A')}`

## Description
A potential security risk was identified by static analysis.
Pattern matched: `{item.get('pattern', 'N/A')}`

## Suggestion
Review this code carefully. Ensure inputs are validated and no secrets are hardcoded.
"""
        _write_issue(output_dir, 'security', item, title, body)

    # Process AI Issues
    for item in report.get('ai_issues', []):
        title = f"AI Found: {item['title']}"
        body = f"""
# {title}

**File**: `{item['file']}:{item.get('line_number', 0)}`
**Difficulty**: {item['difficulty']}
**Type**: {item['type']}

## Description
{item['description']}

## Suggestion
{item['suggestion']}
"""
        _write_issue(output_dir, 'ai', item, title, body)

def _write_issue(output_dir, type_prefix, item, title, body):
    # Create a unique hash for the filename to avoid collisions and keep it short
    hasher = hashlib.md5()
    hasher.update(str(item).encode('utf-8'))
    file_hash = hasher.hexdigest()[:8]
    
    filename = f"issue_{type_prefix}_{file_hash}.md"
    filepath = os.path.join(output_dir, filename)
    
    # Add labels section for GitHub Action to parse if needed
    labels = ', '.join(item.get('tags', []))
    content = f"""---
title: "{title}"
labels: {labels}
---
{body}
"""
    with open(filepath, 'w') as f:
        f.write(content)

def main():
    parser = argparse.ArgumentParser(description='First Issue Generator')
    parser.add_argument('--path', type=str, default='.', help='Path to scan')
    parser.add_argument('--output', type=str, default='./generated_issues', help='Output directory')
    parser.add_argument('--ai', action='store_true', help='Enable AI-based scanning')
    
    args = parser.parse_args()
    
    # Load env vars
    load_dotenv()
    ai_api_key = os.getenv('GEMINI_API_KEY')
    
    if args.ai and not ai_api_key:
        print("Warning: --ai flag provided but GEMINI_API_KEY not found in environment. AI scanning disabled.")
        args.ai = False

    print(f"Scanning codebase at: {args.path}")
    scanner = Scanner(args.path, enable_ai=args.ai, ai_api_key=ai_api_key)
    scanner.scan()
    report = scanner.get_report()
    
    # Filter statistics for ease of reading log
    todos_count = len(report['todos'])
    tests_count = len(report['missing_tests'])
    complex_count = len(report['complex_files'])
    docs_count = len(report['undocumented_functions'])
    
    print(f"Found {todos_count} TODOs")
    print(f"Found {tests_count} missing tests")
    print(f"Found {complex_count} complex files")
    print(f"Found {docs_count} undocumented functions")
    
    security_count = len(report.get('security_issues', []))
    print(f"Found {security_count} security hotspots")
    
    if args.ai:
        ai_count = len(report.get('ai_issues', []))
        print(f"Found {ai_count} AI-detected issues")
    
    print(f"Generating issue templates to: {args.output}")
    generate_issue_files(report, args.output)
    print("Done!")

if __name__ == '__main__':
    main()
