#!/bin/bash
#
# Run Jamf MCP tests and generate remediation report
#
# Usage:
#   ./run_tests.sh
#

cd "$(dirname "$0")"

# Use uv run to ensure dependencies are available
PYTHON=${PYTHON:-"uv run python3"}

echo "======================================"
echo "   Jamf MCP Test & Remediation"
echo "======================================"
echo ""

# Run tests
echo "Running tests..."
$PYTHON test_agent.py --output test_report.json

TEST_EXIT=$?

echo ""
echo "======================================"

# Generate remediation report
$PYTHON remediate.py test_report.json

REMEDIATE_EXIT=$?

# Summary
echo ""
if [ $TEST_EXIT -eq 0 ]; then
    echo "✓ All tests passed!"
else
    echo "✗ Some tests failed. Review remediation_report.json"
    echo ""
    echo "To have Claude fix the issues, run:"
    echo "  claude \"Read CLAUDE.md and remediation_report.json, then fix all failures\""
fi

exit $TEST_EXIT
