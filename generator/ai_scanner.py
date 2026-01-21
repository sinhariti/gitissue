import os
import json
import typing
import google.generativeai as genai
from typing import List, Dict, Any

class AIScanner:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("API Key is required for AI Scanner")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash') # Use flash for speed/cost

    def analyze_file(self, file_path: str, content: str, reason: str = "") -> List[Dict[str, Any]]:
        """
        Sends file content to LLM to find issues.
        """
        prompt = self._create_prompt(file_path, content, reason)
        
        try:
            response = self.model.generate_content(prompt)
            return self._parse_response(response.text, file_path)
        except Exception as e:
            print(f"Error analyzing {file_path}: {e}")
            return []

    def _create_prompt(self, file_path: str, content: str, reason: str = "") -> str:
        focus_area = "General Code Review"
        specific_instructions = ""
        
        if "security_risk" in reason:
            focus_area = "Security Audit"
            specific_instructions = """
            FOCUS EXCLUSIVELY ON SECURITY VULNERABILITIES.
            The scan detected potential risks: {reason}.
            Look for: SQL Injection, Command Injection, path traversal, hardcoded secrets, unsafe deserialization.
            """
        elif "complexity" in reason:
            focus_area = "Refactoring and Clean Code"
            specific_instructions = """
            FOCUS ON SIMPLIFICATION.
            The file was flagged for high complexity.
            Suggest how to break down large functions, reduce nesting, and improve readability.
            """
            
        return f"""
You are an expert code reviewer specializing in {focus_area}. Analyze the following code file: `{file_path}`.

Reason for scan: {reason}

{specific_instructions}

Find potential issues in these categories:
1. **Potential Bugs**: Logic errors, edge cases, off-by-one errors.
2. **Security Vulnerabilities**: Injection risks, unsafe inputs, poor data handling.
3. **Code Quality**: Complex logic that needs refactoring, poor naming, duplication.

Output STRICT JSON only. The format must be a list of objects:
[
  {{
    "title": "Short title of the issue",
    "description": "Detailed description of the problem",
    "suggestion": "How to fix it",
    "line_number": <int> (approximate line number, 0 if general),
    "difficulty": "Easy" | "Medium" | "Hard",
    "type": "bug" | "security" | "refactor"
  }}
]

If no significant issues are found, return an empty list [].

Code Content:
```
{content}
```
"""

    def _parse_response(self, response_text: str, file_path: str) -> List[Dict[str, Any]]:
        cleaned_text = response_text.replace('```json', '').replace('```', '').strip()
        try:
            issues = json.loads(cleaned_text)
            # Add file path to each issue
            for issue in issues:
                issue['file'] = file_path
                issue['tags'] = ['ai-generated', issue['type']]
            return issues
        except json.JSONDecodeError:
            print(f"Failed to parse AI response for {file_path}")
            return []
