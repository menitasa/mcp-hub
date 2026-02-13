# Contributing

Thanks for your interest in contributing to the Jamf MCP Server!

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Running Tests](#running-tests)
- [Adding New Tools](#adding-new-tools)
- [Claude Code Agents](#claude-code-agents)
- [Code Standards](#code-standards)
- [Pull Request Process](#pull-request-process)

---

## Getting Started

1. Fork and clone the repository
2. Set up your development environment
3. Make your changes
4. Run tests to verify
5. Submit a pull request

---

## Development Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/mcp-hub.git
cd mcp-hub

# Install in development mode
uv sync
# or
python3 -m venv venv && source venv/bin/activate && pip install -e .

# Set up test credentials
export JAMF_PRO_URL="https://yourcompany.jamfcloud.com"
export JAMF_PRO_CLIENT_ID="your-client-id"
export JAMF_PRO_CLIENT_SECRET="your-client-secret"
```

---

## Running Tests

### Full Test Suite

```bash
# Recommended
./run_tests.sh

# Or directly
python3 test_agent.py --output test_report.json

# Verbose mode for debugging
python3 test_agent.py --verbose
```

### Verify Test Coverage

```bash
python3 verify_test_coverage.py
```

Ensures all MCP tools have corresponding tests.

### Local Git Hooks

Install pre-push hooks to run tests automatically:

```bash
./scripts/install-hooks.sh
```

Skip with `git push --no-verify` when needed.

### CI/CD

Tests run automatically via GitHub Actions on:
- Pushes to `main`, `develop`, `feature/*`
- Pull requests to `main`
- Manual dispatch

Required repository secrets:
- `JAMF_PRO_URL`
- `JAMF_PRO_CLIENT_ID`
- `JAMF_PRO_CLIENT_SECRET`

---

## Adding New Tools

When adding a new MCP tool:

1. **Implement** in `src/jamf_mcp/tools/<module>.py`
2. **Export** in `src/jamf_mcp/tools/__init__.py`
3. **Register** with `@jamf_tool` decorator
4. **Add test** in `test_agent.py` and include in `run_all_tests()` test_plan
5. **Map test** in `TOOL_TEST_MAPPING` in `verify_test_coverage.py`
6. **Document** in `docs/TOOLS.md` under the appropriate product section

### Tool Template

```python
from ._common import format_response, format_error, get_client
from ._registry import jamf_tool

@jamf_tool
async def jamf_your_tool_name(
    param1: str,
    param2: Optional[int] = None,
) -> str:
    """Brief description of what this tool does.

    Args:
        param1: Description of param1.
        param2: Description of param2.

    Returns:
        JSON string with success status, message, and data.
    """
    client = get_client()
    try:
        result = await client.v1_get("/your/endpoint")
        return format_response(result, "Success message")
    except Exception as e:
        return format_error(str(e))
```

---

## Claude Code Agents

When contributing via [Claude Code](https://claude.ai/code), use the project's specialized agents to ensure consistency and quality. These agents are automatically available and should be used throughout development.

### Available Agents

| Agent | When to Use |
|-------|-------------|
| **jamf-api-lookup** | Before implementing a new tool — verify correct API endpoints, HTTP methods, and request/response schemas |
| **mcp-server-builder** | When adding tools or working with MCP patterns — ensures consistent tool registration and architecture |
| **code-standards-reviewer** | After writing code — reviews for adherence to project standards before committing |
| **test-and-lint-validator** | After implementing features — ensures tests are added and all tests pass |

### Recommended Workflow

1. **Research** — Use `jamf-api-lookup` to verify the correct Jamf API endpoint
2. **Implement** — Use `mcp-server-builder` for guidance on tool structure
3. **Review** — Use `code-standards-reviewer` to check your implementation
4. **Validate** — Use `test-and-lint-validator` to ensure tests pass

### Example

When adding a new tool for Jamf Pro buildings:

```
You: "I need to add a tool to create buildings in Jamf Pro"

1. Claude uses jamf-api-lookup to find POST /JSSResource/buildings endpoint
2. Claude uses mcp-server-builder to implement following project patterns
3. Claude uses code-standards-reviewer to verify the implementation
4. Claude uses test-and-lint-validator to add and run tests
```

These agents help maintain consistency across the codebase and catch issues before they reach code review.

---

## Code Standards

- **Type hints** — All functions should have type annotations
- **Docstrings** — Use Google-style docstrings
- **Error handling** — Use `format_error()` for consistent error responses
- **Naming** — Tools should be prefixed with `jamf_` (Pro) or `jamf_protect_` (Protect)

---

## Pull Request Process

1. **Branch** from `develop` for features, `main` for hotfixes
2. **Test** — Run `./run_tests.sh` and ensure all tests pass
3. **Document** — Update docs if adding/changing tools
4. **Commit** — Use clear, descriptive commit messages
5. **PR** — Target `develop` branch, describe changes clearly

### Commit Message Format

```
feat: add jamf_get_something tool

- Implements GET /api/v1/something endpoint
- Adds test coverage
- Updates TOOLS.md
```

Prefixes: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`
