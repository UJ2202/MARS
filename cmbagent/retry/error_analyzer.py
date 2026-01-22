"""
Error pattern analyzer.

Analyzes errors to categorize them, extract patterns, and provide
fix suggestions based on common error types.
"""

import re
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session


class ErrorAnalyzer:
    """Analyzes errors and provides suggestions"""

    # Common error patterns with regex, category, and suggestions
    ERROR_PATTERNS = {
        "file_not_found": {
            "regex": r"(FileNotFoundError|No such file|cannot find|file.*not.*found)",
            "category": "file_not_found",
            "suggestions": [
                "Verify the file path is correct",
                "Check if the file exists before accessing",
                "Use absolute path instead of relative path",
                "List directory contents to see available files"
            ]
        },
        "api_error": {
            "regex": r"(APIError|API.*failed|rate limit|quota exceeded|authentication.*failed)",
            "category": "api_error",
            "suggestions": [
                "Check API credentials are valid",
                "Verify API endpoint is correct",
                "Check if rate limit was exceeded (wait and retry)",
                "Validate request parameters"
            ]
        },
        "timeout": {
            "regex": r"(timeout|timed out|TimeoutError)",
            "category": "timeout",
            "suggestions": [
                "Increase timeout duration",
                "Check network connectivity",
                "Simplify the operation to complete faster",
                "Implement chunking for large operations"
            ]
        },
        "import_error": {
            "regex": r"(ImportError|ModuleNotFoundError|No module named)",
            "category": "import_error",
            "suggestions": [
                "Install missing package: pip install <package>",
                "Check package name spelling",
                "Verify package is in requirements",
                "Use correct import statement"
            ]
        },
        "type_error": {
            "regex": r"TypeError",
            "category": "type_error",
            "suggestions": [
                "Check argument types match function signature",
                "Verify data type conversions",
                "Handle None values properly",
                "Validate input data types"
            ]
        },
        "value_error": {
            "regex": r"ValueError",
            "category": "value_error",
            "suggestions": [
                "Validate input values are in expected range",
                "Check for empty or invalid data",
                "Verify data format is correct",
                "Handle edge cases"
            ]
        },
        "key_error": {
            "regex": r"KeyError",
            "category": "key_error",
            "suggestions": [
                "Check that dictionary key exists before accessing",
                "Use .get() method with default value",
                "Verify data structure is as expected",
                "Handle missing keys gracefully"
            ]
        },
        "attribute_error": {
            "regex": r"AttributeError",
            "category": "attribute_error",
            "suggestions": [
                "Verify object has the attribute",
                "Check for None objects",
                "Ensure object is of expected type",
                "Use hasattr() to check before accessing"
            ]
        },
        "index_error": {
            "regex": r"IndexError",
            "category": "index_error",
            "suggestions": [
                "Check list/array length before indexing",
                "Verify index is within bounds",
                "Handle empty sequences",
                "Use safe indexing with bounds checking"
            ]
        },
        "permission_error": {
            "regex": r"(PermissionError|Permission denied|Access denied)",
            "category": "permission_error",
            "suggestions": [
                "Check file/directory permissions",
                "Run with appropriate privileges",
                "Verify user has access rights",
                "Check file is not locked by another process"
            ]
        },
        "connection_error": {
            "regex": r"(ConnectionError|Connection refused|Connection reset)",
            "category": "connection_error",
            "suggestions": [
                "Verify service is running",
                "Check network connectivity",
                "Confirm correct host and port",
                "Check firewall settings"
            ]
        },
        "memory_error": {
            "regex": r"(MemoryError|Out of memory|OOM)",
            "category": "memory_error",
            "suggestions": [
                "Process data in smaller chunks",
                "Reduce memory usage",
                "Close unused resources",
                "Optimize data structures"
            ]
        }
    }

    def analyze_error(
        self,
        error_message: str,
        traceback: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze error and return category and suggestions.

        Args:
            error_message: Error message string
            traceback: Full traceback (optional)

        Returns:
            Dictionary with category, suggestions, and pattern info
        """
        # Combine error message and traceback for analysis
        full_error = error_message
        if traceback:
            full_error = f"{error_message}\n{traceback}"

        # Try to match error patterns
        for pattern_name, pattern_info in self.ERROR_PATTERNS.items():
            if re.search(pattern_info["regex"], full_error, re.IGNORECASE):
                return {
                    "category": pattern_info["category"],
                    "pattern": pattern_name,
                    "suggestions": pattern_info["suggestions"],
                    "common_error": True
                }

        # Unknown error pattern
        return {
            "category": "unknown",
            "pattern": None,
            "suggestions": [
                "Review the full error message and traceback",
                "Check recent code changes",
                "Search for similar errors online",
                "Break down the task into smaller steps"
            ],
            "common_error": False
        }

    def get_similar_resolved_errors(
        self,
        db_session: Session,
        error_category: str,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Find similar errors that were successfully resolved.

        Args:
            db_session: Database session
            error_category: Category of current error
            limit: Max number of examples to return

        Returns:
            List of resolved error examples with solutions
        """
        from cmbagent.database.models import WorkflowStep
        from cmbagent.database.states import StepState

        try:
            # Query successful steps that had previous failures in same category
            steps = db_session.query(WorkflowStep).filter(
                WorkflowStep.status == StepState.COMPLETED.value
            ).all()

            resolved_errors = []

            for step in steps:
                # Check if step has retry attempts
                retry_attempts = step.meta.get("retry_attempts", [])
                if len(retry_attempts) > 1:
                    # Check if any attempt had matching error category
                    for attempt in retry_attempts[:-1]:  # Exclude last (successful) attempt
                        if attempt.get("error_type"):
                            # Analyze the error from the attempt
                            attempt_error = attempt.get("error_message", "")
                            attempt_analysis = self.analyze_error(attempt_error)

                            if attempt_analysis["category"] == error_category:
                                # Found a similar error that was resolved
                                resolved_errors.append({
                                    "step_id": str(step.id),
                                    "description": f"Similar {error_category} in step {step.step_number}",
                                    "original_error": attempt_error[:100],  # Truncate
                                    "solution": "Task completed successfully after retry with context",
                                    "attempts": len(retry_attempts)
                                })

                                if len(resolved_errors) >= limit:
                                    return resolved_errors

            return resolved_errors

        except Exception as e:
            # If query fails, return empty list
            print(f"Warning: Could not query similar errors: {e}")
            return []

    def estimate_success_probability(
        self,
        attempt_number: int,
        error_category: str,
        has_user_feedback: bool
    ) -> float:
        """
        Estimate probability of success for next retry.

        Args:
            attempt_number: Current attempt number
            error_category: Type of error
            has_user_feedback: Whether user provided guidance

        Returns:
            Probability between 0.0 and 1.0
        """
        # Base probability decreases with attempts
        base_prob = 1.0 / (attempt_number + 1)

        # Boost if user provided feedback
        if has_user_feedback:
            base_prob *= 1.5

        # Adjust based on error category
        category_multipliers = {
            "file_not_found": 0.8,  # Often requires external fix
            "api_error": 0.6,       # May be external service issue
            "timeout": 0.7,         # May resolve with retry
            "import_error": 0.9,    # Usually fixable
            "type_error": 0.85,     # Code fix needed
            "value_error": 0.85,    # Code fix needed
            "key_error": 0.85,      # Code fix needed
            "attribute_error": 0.80, # Code fix needed
            "index_error": 0.85,    # Code fix needed
            "permission_error": 0.5, # Often requires external fix
            "connection_error": 0.7, # May be transient
            "memory_error": 0.6,    # May require significant changes
            "unknown": 0.5          # Uncertain
        }

        multiplier = category_multipliers.get(error_category, 0.5)
        probability = min(base_prob * multiplier, 1.0)

        return round(probability, 2)

    def extract_file_paths_from_error(self, error_message: str) -> List[str]:
        """
        Extract file paths mentioned in error message.

        Args:
            error_message: Error message

        Returns:
            List of file paths found in error
        """
        # Common file path patterns
        patterns = [
            r'[\'"]([/\\][\w/\\.-]+)[\'"]',  # Quoted paths
            r'File "([^"]+)"',                # Python traceback format
            r'at ([/\\][\w/\\.-]+):',        # Location format
        ]

        paths = []
        for pattern in patterns:
            matches = re.findall(pattern, error_message)
            paths.extend(matches)

        return list(set(paths))  # Remove duplicates

    def suggest_alternative_approaches(
        self,
        error_category: str,
        task_description: str
    ) -> List[str]:
        """
        Suggest alternative approaches based on error type.

        Args:
            error_category: Type of error
            task_description: Original task description

        Returns:
            List of alternative approaches to try
        """
        alternatives = {
            "file_not_found": [
                "Create the missing file first",
                "Use a different file that exists",
                "Check the working directory",
            ],
            "api_error": [
                "Try a different API endpoint",
                "Use cached data if available",
                "Implement fallback mechanism",
            ],
            "timeout": [
                "Split into smaller operations",
                "Use async/parallel processing",
                "Increase resource limits",
            ],
            "import_error": [
                "Install the required package",
                "Use an alternative library",
                "Implement the functionality directly",
            ],
            "memory_error": [
                "Process data in batches",
                "Use generators instead of lists",
                "Optimize data structures",
            ],
        }

        return alternatives.get(error_category, [
            "Try a different approach",
            "Simplify the task",
            "Break down into smaller steps",
        ])
