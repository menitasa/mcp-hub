# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Quick Reference Commands

```bash
# Run full test suite (41 tests)
./run_tests.sh
# Or directly:
python3 test_agent.py --output test_report.json

# Verify all MCP tools have test coverage
python3 verify_test_coverage.py

# Run server locally (for debugging/development - MCP clients auto-start the server)
uv run jamf-mcp

# Run single test (manually invoke specific test method)
python3 -c "
import asyncio
from test_agent import JamfMCPTestAgent
agent = JamfMCPTestAgent()
asyncio.run(agent.test_get_computers_list())
"
```

## Architecture Overview

This is an MCP (Model Context Protocol) server that enables LLMs to interact with Jamf Pro's API for Apple device management.

### Core Flow

```
Claude (MCP Client) → FastMCP Server (server.py) → Tool Functions (tools/*.py) → JamfClient (client.py) → Jamf Pro API
```

### Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| MCP Server | `src/jamf_mcp/server.py` | FastMCP entry point, tool registration with `@mcp.tool()` |
| API Client | `src/jamf_mcp/client.py` | HTTP client with methods for Classic (`/JSSResource`), v1, v2, v3 APIs |
| Auth | `src/jamf_mcp/auth.py` | OAuth client credentials flow |
| Tool Modules | `src/jamf_mcp/tools/*.py` | Domain-specific tool implementations |
| Test Agent | `test_agent.py` | Integration tests against live Jamf Pro instance |

### API Architecture

The Jamf Pro API uses different versions for different resources:

| API | Endpoint Pattern | Format | Used For |
|-----|------------------|--------|----------|
| Classic | `/JSSResource/...` | XML for POST/PUT | Users, groups, policies, profiles |
| v1 | `/api/v1/...` | JSON | Computers, scripts, categories, app installers |
| v2 | `/api/v2/...` | JSON | Mobile devices, mobile device prestages |
| v3 | `/api/v3/...` | JSON | Computer prestages |

The `JamfClient` class provides methods for each: `classic_get()`, `classic_post()`, `v1_get()`, `v1_post()`, `v2_get()`, `v3_get()`, etc.

## Critical Rules

### After Any Code Changes

Run tests before considering work complete:
```bash
./run_tests.sh
```

### Adding a New MCP Tool

1. Add implementation in appropriate `src/jamf_mcp/tools/<module>.py`
2. Export in `src/jamf_mcp/tools/__init__.py`
3. Register with `@mcp.tool()` in `src/jamf_mcp/server.py`
4. Add test in `test_agent.py` and include in `run_all_tests()` test_plan
5. Add tool-to-test mapping in `TOOL_TEST_MAPPING` in `verify_test_coverage.py`
6. Update README.md "Available Tools" section

### Removing a Tool

Reverse the above steps - remove from all listed files.

### Looking Up Jamf API Endpoints

Source of truth: `https://developer.jamf.com/`

The `jamf_docs_mcp/` directory contains an MCP server that queries the official Jamf documentation. Use it to verify correct endpoints before implementing tools.

#### Quick Lookup Commands

```bash
# Search for endpoints by keyword
cd jamf_docs_mcp && python3 -c "
import asyncio
from src.jamf_docs_mcp.server import search_jamf_api
asyncio.run(search_jamf_api('buildings'))
"

# Get endpoint details
cd jamf_docs_mcp && python3 -c "
import asyncio
from src.jamf_docs_mcp.server import get_endpoint_details
asyncio.run(get_endpoint_details('/JSSResource/buildings', 'GET', 'Classic API'))
"

# Get request body schema (for POST/PUT)
cd jamf_docs_mcp && python3 -c "
import asyncio
from src.jamf_docs_mcp.server import get_request_body_schema
asyncio.run(get_request_body_schema('/JSSResource/buildings/id/0', 'POST', 'Classic API'))
"
```

#### Available jamf_docs_mcp Tools

| Tool | Purpose |
|------|---------|
| `search_jamf_api(pattern)` | Search for endpoints by keyword |
| `list_api_endpoints(spec_title)` | List all endpoints for an API spec |
| `get_endpoint_details(path, method, spec)` | Get full endpoint documentation |
| `get_request_body_schema(path, method, spec)` | Get request body JSON schema |
| `get_response_schema(path, method, spec)` | Get response JSON schema |

#### Common spec_title Values

- `"Jamf Pro API"` for `/api/v1`, `/api/v2`, `/api/v3`
- `"Classic API"` for `/JSSResource`

#### Claude Agent for API Lookup

Use the `jamf-api-lookup` agent (`.claude/agents/jamf-api-lookup.md`) when implementing new tools to verify correct endpoints and schemas.

## Behavioral Guidelines for Using the MCP Tools

### Always Ask to Clarify Device Type

When a user request doesn't specify device type, ask which they mean:
- "Show all devices" → Ask: computers (macOS) or mobile devices (iOS/iPadOS)?
- "Create a smart group" → Ask: computer or mobile device smart group?
- "Get extension attributes" → Ask: computer, mobile_device, or user EAs?

### Before Deploying to "All Devices"

1. Check if default smart groups already exist (e.g., "All Managed Clients" ID: 1)
2. Present existing groups with membership counts before creating new ones
3. Require explicit confirmation: "This will deploy to X devices. Confirm?"
4. Suggest phased rollout testing first

### Resource Creation Order

When creating multiple dependent resources, follow this order:
1. Category
2. Extension Attribute
3. Package/Script
4. Smart/Static Group
5. Deployment (Policy/Profile/App)

## Deployment Scope Analysis

**Important:** List endpoints don't include scope data. To find what's deployed to a group:

1. Get list of deployments (returns IDs only)
2. Fetch each deployment by ID to get scope
3. Check each deployment type: policies, profiles, app installers, Mac apps, mobile apps, restricted software, eBooks, patch policies

## Smart Group Criteria Reference

### Search Types
`is`, `is not`, `like`, `not like`, `has`, `does not have`, `greater than`, `less than`, `greater than or equal`, `less than or equal`, `matches regex`, `does not match regex`, `member of`, `not member of`

### Common Criterion Names (Computers)
- General: UDID, Computer Name, Serial Number, Department, Building
- Hardware: Model, Model Identifier, Architecture Type, Total RAM MB
- OS: Operating System Version, Operating System Build
- Security: FileVault 2 Status, SIP Status, Gatekeeper Status
- Management: Last Inventory Update, Enrolled via DEP, User Approved MDM

### Example Criteria

```json
// Match all Macs
{"name": "UDID", "value": "", "search_type": "like"}

// macOS 14.x
{"name": "Operating System Version", "value": "14.", "search_type": "like"}

// OR-chain with default_conjunction="or"
[
  {"name": "Processor Type", "value": "M3", "search_type": "like"},
  {"name": "Processor Type", "value": "M4", "search_type": "like"}
]
```

## API Endpoints Reference

### Jamf Pro API
| Resource | Endpoint |
|----------|----------|
| Computers List | `GET /api/v1/computers-inventory` |
| Computer Detail | `GET /api/v1/computers-inventory-detail/{id}` |
| Mobile Devices | `GET /api/v2/mobile-devices` |
| Scripts | `GET /api/v1/scripts` |
| App Installer Titles | `GET /api/v1/app-installers/titles` |
| App Installer Deployments | `GET /api/v1/app-installers/deployments` |
| Computer PreStages | `GET /api/v3/computer-prestages` |
| Mobile Device PreStages | `GET /api/v2/mobile-device-prestages` |
| API Roles | `GET /api/v1/api-roles` |
| API Integrations | `GET /api/v1/api-integrations` |

### Classic API
| Resource | Endpoint |
|----------|----------|
| Users | `GET /JSSResource/users` |
| Computer Groups | `GET /JSSResource/computergroups` |
| Mobile Groups | `GET /JSSResource/mobiledevicegroups` |
| Policies | `GET /JSSResource/policies` |
| Categories | `GET /JSSResource/categories` |
| Buildings | `GET /JSSResource/buildings` |
| Departments | `GET /JSSResource/departments` |
| Computer EAs | `GET /JSSResource/computerextensionattributes` |
| Computer Profiles | `GET /JSSResource/osxconfigurationprofiles` |

## Troubleshooting Tests

### Remediation Map

| Test Category | Primary File | Secondary |
|---------------|--------------|-----------|
| Authentication | `auth.py` | `.env` credentials |
| Computers | `tools/computers.py` | `client.py` |
| Mobile Devices | `tools/mobile_devices.py` | `client.py` |
| Users | `tools/users.py` | `client.py` |
| Groups | `tools/groups.py` | `client.py` |
| Policies | `tools/policies.py` | `client.py` |
| App Installers | `tools/app_installers.py` | `client.py` |
| Profiles | `tools/profiles.py` | `client.py` |
| Scripts | `tools/scripts.py` | `client.py` |
| Extension Attributes | `tools/extension_attributes.py` | `client.py` |
| PreStages | `tools/prestages.py` | `client.py` |
| Categories | `tools/categories.py` | `client.py` |
| Buildings/Departments | `tools/locations.py` | `client.py` |
| Apps (Mac/Mobile/eBooks/etc) | `tools/apps.py` | `client.py` |
| API Roles | `tools/api_roles.py` | `client.py` |

### Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `401 Unauthorized` | Invalid credentials | Check `.env` JAMF_PRO_CLIENT_ID/SECRET |
| `404 Not Found` | Wrong endpoint path | Verify API path in tools module |
| `400 Bad Request` | Malformed body | Check JSON/XML structure |
| `KeyError: 'results'` | Response format mismatch | Update response parsing |

## Environment Variables

Required in `.env`:
```
JAMF_PRO_URL=https://yourcompany.jamfcloud.com
JAMF_PRO_CLIENT_ID=your-client-id
JAMF_PRO_CLIENT_SECRET=your-client-secret
```