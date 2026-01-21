import os
import re
import time
from typing import List, Dict, Any

class Scanner:
    def __init__(self, root_path: str, enable_ai: bool = False, ai_api_key: str = None):
        self.root_path = root_path
        self.enable_ai = enable_ai
        self.ai_scanner = None
        if enable_ai and ai_api_key:
            from generator.ai_scanner import AIScanner
            self.ai_scanner = AIScanner(ai_api_key)
            
        self.todos = []
        self.missing_tests = []
        self.complex_files = []
        self.undocumented_functions = []
        self.security_issues = []
        self.ai_issues = []

    def scan(self):
        for root, _, files in os.walk(self.root_path):
            if '.git' in root or '__pycache__' in root or 'venv' in root:
                continue
            
            for file in files:
                if file.endswith(('.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.h')):
                    file_path = os.path.join(root, file)
                    self._scan_file(file_path)
                    
            # Check for missing tests (heuristic: only for Python files for now)
            for file in files:
                if file.endswith('.py') and not file.startswith('test_') and not file.endswith('_test.py'):
                     self._check_missing_test(root, file)

    def _scan_file(self, file_path: str):
        MAX_SCAN_LINES = 1000  # Limit scanning to first 1000 lines
        lines_to_scan = []
        total_lines = 0

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    total_lines += 1
                    if len(lines_to_scan) < MAX_SCAN_LINES:
                        lines_to_scan.append(line.rstrip('\n'))
            
            self._find_todos(file_path, lines_to_scan)
            self._check_complexity(file_path, total_lines)
            
            nesting_found = self._check_nesting_depth(file_path, lines_to_scan)
            security_found, security_reasons = self._check_security_patterns(file_path, lines_to_scan)

            if file_path.endswith('.py'):
                self._check_docs(file_path, lines_to_scan)

            if self.enable_ai and self.ai_scanner:
                should_scan, reason = self._is_candidate_for_ai(file_path, total_lines, nesting_found, security_found, security_reasons)
                if should_scan:
                    self._scan_with_ai(file_path, "\n".join(lines_to_scan), reason)
                    
        except UnicodeDecodeError:
            pass # Skip binary files or weird encodings

    def _find_todos(self, file_path: str, lines: List[str]):
        todo_pattern = re.compile(r'(\#|//)\s*TODO:?\s*(.*)', re.IGNORECASE)
        beginner_keywords = ['easy', 'beginner', 'good first issue', 'simple', 'cleanup', 'doc']
        
        for i, line in enumerate(lines):
            match = todo_pattern.search(line)
            if match:
                content = match.group(2).strip()
                is_beginner = any(k in content.lower() for k in beginner_keywords)
                
                self.todos.append({
                    'file': file_path,
                    'line': i + 1,
                    'content': content,
                    'difficulty': 'Easy' if is_beginner else 'Unknown',
                    'tags': ['good first issue'] if is_beginner else []
                })

    def _check_missing_test(self, root: str, file: str):
        # Basic heuristic: expecting test_file.py or file_test.py in the same folder 
        # or in a tests folder.
        file_path = os.path.join(root, file)
        
        # Check file size first - if it's huge, writing tests is hard for a beginner
        line_count = 0
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for _ in f:
                    line_count += 1
        except:
            return # Skip if can't read

        base_name = os.path.splitext(file)[0]
        test_candidates = [f'test_{base_name}.py', f'{base_name}_test.py']
        
        has_test = False
        # Check same dir
        for cand in test_candidates:
            if os.path.exists(os.path.join(root, cand)):
                has_test = True
                break
        
        # Check 'tests' subfolder if it didn't exist in same dir
        if not has_test:
             tests_path = os.path.join(self.root_path, 'tests')
             for cand in test_candidates:
                 if os.path.exists(os.path.join(tests_path, cand)):
                     has_test = True
                     break

        if not has_test:
            # Only suggest as beginner issue if file is small
            is_beginner = line_count < 100
            self.missing_tests.append({
                'file': file_path,
                'difficulty': 'Easy' if is_beginner else 'Medium',
                'tags': ['good first issue', 'testing'] if is_beginner else ['testing']
            })

    def _check_complexity(self, file_path: str, line_count: int):
        if line_count > 300:
            self.complex_files.append({
                'file': file_path,
                'lines': line_count,
                'reason': 'File too long (> 300 lines)',
                'difficulty': 'Hard',
                'tags': ['refactor']
            })

    def _check_docs(self, file_path: str, lines: List[str]):
        # Very simple regex-based check for missing docstrings in python functions
        
        for i, line in enumerate(lines):
            if line.strip().startswith('def '):
                func_name = line.split('def ')[1].split('(')[0]
                if func_name.startswith('_'): # Skip private functions
                    continue
                    
                # Look ahead for docstring
                found_doc = False
                for j in range(i + 1, len(lines)):
                    stripped = lines[j].strip()
                    if not stripped:
                        continue
                    if stripped.startswith('"""') or stripped.startswith("'''"):
                        found_doc = True
                    break
                
                if not found_doc:
                    self.undocumented_functions.append({
                        'file': file_path,
                        'line': i + 1,
                        'function': func_name,
                        'difficulty': 'Easy',
                        'tags': ['good first issue', 'documentation']
                    })

    def _scan_with_ai(self, file_path: str, content: str, reason: str = ""):
        time.sleep(4) # Rate limit: 15 RPM = 1 request every 4 seconds
        issues = self.ai_scanner.analyze_file(file_path, content, reason)
        self.ai_issues.extend(issues)

    def _check_nesting_depth(self, file_path: str, lines: List[str]) -> bool:
        # Check for deep nesting (indentation > 16 spaces or 4 tabs approx)
        max_depth = 0
        for line in lines:
            stripped = line.lstrip()
            if not stripped or stripped.startswith('#'):
                continue
            indent = len(line) - len(stripped)
            if indent > 20: # Arbitrary threshold for "deeply nested"
                max_depth = indent
                
        if max_depth > 20:
            self.complex_files.append({
                'file': file_path,
                'lines': len(lines), # Approx
                'reason': 'Deep nesting detected',
                'difficulty': 'Hard',
                'tags': ['refactor', 'complexity']
            })
            return True
        return False

    def _check_security_patterns(self, file_path: str, lines: List[str]) -> (bool, List[str]):
        patterns = {
            'eval_usage': r'eval\s*\(',
            'subprocess_shell': r'subprocess\..*shell=True',
            'hardcoded_password': r'(password|secret|key)\s*=\s*[\'"][^\'"]+[\'"]',
            'noqa_blind': r'#\s*noqa(?!\s*:)'
        }
        
        found_issues = []
        content = "\n".join(lines)
        
        for name, pattern in patterns.items():
            if re.search(pattern, content, re.IGNORECASE):
                found_issues.append(name)
                self.security_issues.append({
                    'file': file_path,
                    'issue': f"Potential security risk: {name}",
                    'pattern': pattern,
                    'difficulty': 'Medium',
                    'tags': ['security', 'security-audit']
                })
        
        return len(found_issues) > 0, found_issues

    def _is_candidate_for_ai(self, file_path: str, total_lines: int, nesting_found: bool, security_found: bool, security_reasons: List[str]) -> (bool, str):
        # Decision logic for targeted AI scan
        if security_found:
            return True, f"security_risk: {', '.join(security_reasons)}"
        
        if nesting_found or total_lines > 200:
            return True, "high_complexity"
            
        # Random sampling or other heuristics could go here
        # For now, we are being conservative to save tokens
        
        return False, ""

    def get_report(self) -> Dict[str, Any]:
        return {
            'todos': self.todos,
            'missing_tests': self.missing_tests,
            'complex_files': self.complex_files,
            'undocumented_functions': self.undocumented_functions,
            'security_issues': self.security_issues,
            'ai_issues': self.ai_issues
        }
