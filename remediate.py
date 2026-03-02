#!/usr/bin/env python3
# Copyright 2026, Jamf Software LLC
"""
Jamf MCP Auto-Remediation Script

Reads test results and outputs a remediation report for the AI agent.
Can be run after test_agent.py to analyze failures.

Usage:
    python remediate.py                    # Uses latest test report
    python remediate.py test_report.json   # Uses specific report
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'


# Mapping of test categories to source files
FILE_MAP = {
    "Authentication": {
        "primary": "src/jamf_mcp/auth.py",
        "secondary": ["test_agent.py"]
    },
    "Computers": {
        "primary": "src/jamf_mcp/tools/computers.py",
        "secondary": ["src/jamf_mcp/client.py"]
    },
    "Mobile Devices": {
        "primary": "src/jamf_mcp/tools/mobile_devices.py",
        "secondary": ["src/jamf_mcp/client.py"]
    },
    "Users": {
        "primary": "src/jamf_mcp/tools/users.py",
        "secondary": ["src/jamf_mcp/client.py"]
    },
    "Smart Groups": {
        "primary": "src/jamf_mcp/tools/groups.py",
        "secondary": ["src/jamf_mcp/client.py"]
    },
    "Static Groups": {
        "primary": "src/jamf_mcp/tools/groups.py",
        "secondary": ["src/jamf_mcp/client.py"]
    },
    "Policies": {
        "primary": "src/jamf_mcp/tools/policies.py",
        "secondary": ["src/jamf_mcp/client.py"]
    },
    "App Installers": {
        "primary": "src/jamf_mcp/tools/app_installers.py",
        "secondary": ["src/jamf_mcp/client.py"]
    },
    "Configuration Profiles": {
        "primary": "src/jamf_mcp/tools/profiles.py",
        "secondary": ["src/jamf_mcp/client.py"]
    },
    "Scripts": {
        "primary": "src/jamf_mcp/tools/scripts.py",
        "secondary": ["src/jamf_mcp/client.py"]
    },
    "Extension Attributes": {
        "primary": "src/jamf_mcp/tools/extension_attributes.py",
        "secondary": ["src/jamf_mcp/client.py"]
    },
    "Categories": {
        "primary": "src/jamf_mcp/tools/categories.py",
        "secondary": ["src/jamf_mcp/client.py"]
    },
    "PreStage Enrollments": {
        "primary": "src/jamf_mcp/tools/prestages.py",
        "secondary": ["src/jamf_mcp/client.py"]
    },
    "Mac Apps": {
        "primary": "src/jamf_mcp/tools/apps.py",
        "secondary": ["src/jamf_mcp/client.py"]
    },
    "Mobile Device Apps": {
        "primary": "src/jamf_mcp/tools/apps.py",
        "secondary": ["src/jamf_mcp/client.py"]
    },
    "Restricted Software": {
        "primary": "src/jamf_mcp/tools/apps.py",
        "secondary": ["src/jamf_mcp/client.py"]
    },
    "eBooks": {
        "primary": "src/jamf_mcp/tools/apps.py",
        "secondary": ["src/jamf_mcp/client.py"]
    },
    "Patch Policies": {
        "primary": "src/jamf_mcp/tools/apps.py",
        "secondary": ["src/jamf_mcp/client.py"]
    },
}

# Error patterns and suggested fixes
ERROR_PATTERNS = {
    "401": {
        "cause": "Invalid or expired credentials",
        "fix": "Check JAMF_PRO_CLIENT_ID and JAMF_PRO_CLIENT_SECRET in .env file"
    },
    "403": {
        "cause": "Insufficient API permissions",
        "fix": "Add required permissions to API client in Jamf Pro"
    },
    "404": {
        "cause": "Endpoint not found or wrong path",
        "fix": "Verify API endpoint path matches Jamf Pro API documentation"
    },
    "400": {
        "cause": "Malformed request body",
        "fix": "Check JSON structure being sent to the API"
    },
    "500": {
        "cause": "Jamf Pro server error",
        "fix": "Check Jamf Pro server status, may be temporary"
    },
    "KeyError": {
        "cause": "Unexpected response format",
        "fix": "Update response parsing to handle actual API response structure"
    },
    "TypeError": {
        "cause": "None value or type mismatch",
        "fix": "Add null checks and type validation"
    },
    "Connection": {
        "cause": "Network or URL issue",
        "fix": "Verify JAMF_PRO_URL is correct and accessible"
    },
}


def find_latest_report() -> Optional[Path]:
    """Find the most recent test report file"""
    project_dir = Path(__file__).parent

    # Check for test_report.json first
    default_report = project_dir / "test_report.json"
    if default_report.exists():
        return default_report

    # Find most recent jamf_test_report_*.json
    reports = list(project_dir.glob("jamf_test_report_*.json"))
    if reports:
        return max(reports, key=lambda p: p.stat().st_mtime)

    return None


def analyze_error(error: str) -> dict:
    """Analyze error message and return diagnosis"""
    for pattern, info in ERROR_PATTERNS.items():
        if pattern.lower() in error.lower():
            return {
                "pattern": pattern,
                "cause": info["cause"],
                "fix": info["fix"]
            }

    return {
        "pattern": "Unknown",
        "cause": "Unrecognized error pattern",
        "fix": "Review error message and check related code"
    }


def generate_remediation_report(report_path: Path) -> dict:
    """Generate a remediation report from test results"""
    with open(report_path) as f:
        data = json.load(f)

    summary = data.get("summary", {})
    results = data.get("results", [])

    failures = [r for r in results if r.get("status") == "FAILED"]

    remediation = {
        "report_file": str(report_path),
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_tests": summary.get("total", 0),
            "passed": summary.get("passed", 0),
            "failed": summary.get("failed", 0),
            "skipped": summary.get("skipped", 0),
        },
        "failures": [],
        "files_to_check": set(),
    }

    for failure in failures:
        error = failure.get("error", "Unknown error")
        category = failure.get("category", "Unknown")
        analysis = analyze_error(error)

        file_info = FILE_MAP.get(category, {"primary": "Unknown", "secondary": []})

        failure_info = {
            "test": failure.get("name"),
            "category": category,
            "error": error,
            "analysis": analysis,
            "primary_file": file_info["primary"],
            "secondary_files": file_info["secondary"],
        }

        remediation["failures"].append(failure_info)
        remediation["files_to_check"].add(file_info["primary"])
        for f in file_info["secondary"]:
            remediation["files_to_check"].add(f)

    remediation["files_to_check"] = list(remediation["files_to_check"])

    return remediation


def print_remediation_report(remediation: dict):
    """Print formatted remediation report"""
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'JAMF MCP AUTO-REMEDIATION REPORT':^70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}")

    summary = remediation["summary"]
    print(f"\n{Colors.CYAN}Test Summary:{Colors.ENDC}")
    print(f"  Total: {summary['total_tests']} | ", end="")
    print(f"{Colors.GREEN}Passed: {summary['passed']}{Colors.ENDC} | ", end="")
    print(f"{Colors.RED}Failed: {summary['failed']}{Colors.ENDC} | ", end="")
    print(f"{Colors.YELLOW}Skipped: {summary['skipped']}{Colors.ENDC}")

    if not remediation["failures"]:
        print(f"\n{Colors.GREEN}{Colors.BOLD}All tests passed! No remediation needed.{Colors.ENDC}\n")
        return

    print(f"\n{Colors.RED}{Colors.BOLD}Failures Requiring Remediation:{Colors.ENDC}")
    print(f"{Colors.DIM}{'-' * 70}{Colors.ENDC}")

    for i, failure in enumerate(remediation["failures"], 1):
        print(f"\n{Colors.RED}[{i}] {failure['test']}{Colors.ENDC}")
        print(f"    {Colors.DIM}Category:{Colors.ENDC} {failure['category']}")
        print(f"    {Colors.DIM}Error:{Colors.ENDC} {failure['error'][:80]}{'...' if len(failure['error']) > 80 else ''}")
        print(f"    {Colors.YELLOW}Cause:{Colors.ENDC} {failure['analysis']['cause']}")
        print(f"    {Colors.GREEN}Fix:{Colors.ENDC} {failure['analysis']['fix']}")
        print(f"    {Colors.CYAN}Primary File:{Colors.ENDC} {failure['primary_file']}")
        if failure['secondary_files']:
            print(f"    {Colors.CYAN}Also Check:{Colors.ENDC} {', '.join(failure['secondary_files'])}")

    print(f"\n{Colors.DIM}{'-' * 70}{Colors.ENDC}")
    print(f"\n{Colors.CYAN}{Colors.BOLD}Files to Review:{Colors.ENDC}")
    for f in remediation["files_to_check"]:
        print(f"  - {f}")

    print(f"\n{Colors.YELLOW}{Colors.BOLD}Next Steps:{Colors.ENDC}")
    print("  1. Review the files listed above")
    print("  2. Apply the suggested fixes")
    print("  3. Re-run tests: python test_agent.py")
    print()


def save_remediation_json(remediation: dict, output_path: Path):
    """Save remediation report as JSON for AI agent consumption"""
    with open(output_path, 'w') as f:
        json.dump(remediation, f, indent=2)
    print(f"{Colors.DIM}Remediation report saved to: {output_path}{Colors.ENDC}")


def main():
    # Find report file
    if len(sys.argv) > 1:
        report_path = Path(sys.argv[1])
    else:
        report_path = find_latest_report()

    if not report_path or not report_path.exists():
        print(f"{Colors.RED}Error: No test report found.{Colors.ENDC}")
        print("Run tests first: python test_agent.py --output test_report.json")
        sys.exit(1)

    print(f"{Colors.DIM}Reading: {report_path}{Colors.ENDC}")

    # Generate remediation report
    remediation = generate_remediation_report(report_path)

    # Print human-readable report
    print_remediation_report(remediation)

    # Save JSON for AI agent
    output_path = Path(__file__).parent / "remediation_report.json"
    save_remediation_json(remediation, output_path)

    # Exit with appropriate code
    sys.exit(1 if remediation["failures"] else 0)


if __name__ == "__main__":
    main()
