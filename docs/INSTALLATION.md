# Installation & Configuration

## Table of Contents

- [Prerequisites](#prerequisites)
- [Automated Setup (Recommended)](#automated-setup-recommended)
- [Quick Start (Zero-Credential)](#quick-start-zero-credential)
- [Installation](#installation)
- [Running the Server Manually (Optional)](#running-the-server-manually-optional)
- [Environment Variables](#environment-variables)
  - [Jamf Pro (Optional)](#jamf-pro-optional)
  - [Jamf Protect (Optional)](#jamf-protect-optional)
  - [Jamf Security Cloud (Optional)](#jamf-security-cloud-optional)
- [Jamf Pro API Setup](#setting-up-api-credentials-in-jamf-pro)
- [Client Configuration](#client-configuration)
  - [Claude Desktop (macOS)](#claude-desktop-macos)
  - [Claude Desktop (Windows)](#claude-desktop-windows)
  - [Claude Code CLI](#claude-code-cli)
  - [Other MCP Clients](#other-mcp-clients)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

- **Python 3.10+**
- **Jamf instance** (optional - server starts in onboarding mode without credentials)

---

## Automated Setup (Recommended)

The `setup.sh` script handles everything — creating API credentials in Jamf Pro and configuring Claude Desktop — in a single interactive walkthrough.

### Prerequisites

- `curl` (pre-installed on macOS)
- [`uv`](https://github.com/astral-sh/uv) — install with: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- A Jamf Pro admin account (used once to create API credentials, then discarded)

### Running Setup

```bash
cd /path/to/mcp-hub
bash setup.sh
```

### What It Does

1. **Prompts for your Jamf Pro URL and admin credentials** (credentials are used only during setup and cleared immediately after)
2. **Authenticates** to Jamf Pro and fetches available API privileges
3. **Lets you choose privilege scope** — either all privileges (recommended) or pick categories individually (Computers, Mobile Devices, Policies, etc.)
4. **Creates an API Role** in Jamf Pro with the selected privileges
5. **Creates an API Integration** linked to that role
6. **Generates client credentials** (Client ID + Client Secret)
7. **Writes the Claude Desktop config** (`~/Library/Application Support/Claude/claude_desktop_config.json`), preserving any existing MCP servers you already have configured

### After Setup

1. **Restart Claude Desktop** (or your MCP client)
2. Ask Claude: **"What's the setup status?"** to verify connectivity

> **Note:** If you already have a `claude_desktop_config.json` with other MCP servers, the script will detect them and ask how to merge — it won't overwrite your existing configuration.

---

## Quick Start (Zero-Credential)

If you prefer manual configuration, the server starts with **zero credentials required**. Use the built-in setup tools to get started:

1. **Configure your MCP client** (see [Client Configuration](#client-configuration) below)
2. **Restart your MCP client** — it automatically starts the server for you
3. **Ask Claude** to help you get set up:
   - "What's the setup status?" → calls `jamf_get_setup_status()`
   - "How do I configure Jamf Pro?" → calls `jamf_configure_help(product="jamf_pro")`

### How MCP Server Startup Works

**You don't need to manually run the server.** MCP clients (Claude Desktop, Claude Code, etc.) automatically start configured servers when they launch. The client configuration tells the client *how* to start the server — you just configure it once and the client handles the rest.

### Onboarding Tools

| Tool | Description |
|------|-------------|
| `jamf_get_setup_status` | Shows which products are configured and ready |
| `jamf_configure_help` | Provides step-by-step setup instructions |

These tools work **without any credentials** and help you configure each product.

---

## Installation

Choose an installation method below. After installing, proceed to [Client Configuration](#client-configuration) to set up your MCP client.

### Option 1: Using uv (Recommended)

[uv](https://github.com/astral-sh/uv) handles dependencies automatically — no separate install step needed. Just configure your MCP client to use `uv run`.

### Option 2: pip with Virtual Environment

```bash
cd /path/to/mcp-hub
python3 -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -e .
```

### Option 3: System pip

```bash
cd /path/to/mcp-hub
pip3 install -e .
```

---

## Running the Server Manually (Optional)

**Most users don't need this section.** MCP clients automatically start the server — see [Client Configuration](#client-configuration).

Manual execution is useful for:
- **Debugging** — See error messages and stack traces directly
- **Development** — Test changes before configuring clients
- **Troubleshooting** — Verify the server starts without client complexity

```bash
# Using uv
uv run jamf-mcp

# Using venv
source venv/bin/activate && jamf-mcp

# Using system pip
python3 -m jamf_mcp.server
```

The server communicates via stdio, so you'll see initialization messages but no prompt. Press `Ctrl+C` to stop.

---

## Environment Variables

All products are optional. Configure the ones you need.

### Jamf Pro (Optional)

| Variable | Description |
|----------|-------------|
| `JAMF_PRO_URL` | Your Jamf Pro URL (e.g., `https://yourcompany.jamfcloud.com`) |
| `JAMF_PRO_CLIENT_ID` | OAuth API client ID |
| `JAMF_PRO_CLIENT_SECRET` | OAuth API client secret |

### Jamf Protect (Optional)

Required for Protect tools (`jamf_protect_*`):

| Variable | Description |
|----------|-------------|
| `JAMF_PROTECT_URL` | Jamf Protect API URL (e.g., `https://yourorg.protect.jamfcloud.com/graphql`) |
| `JAMF_PROTECT_CLIENT_ID` | Jamf Protect API client ID |
| `JAMF_PROTECT_PASSWORD` | Jamf Protect API client password |

### Jamf Security Cloud (Optional)

Required for RISK API tools (`jamf_get_risk_devices`, `jamf_override_device_risk`):

| Variable | Description |
|----------|-------------|
| `JAMF_SECURITY_URL` | Security Cloud URL (e.g., `https://radar.wandera.com`) |
| `JAMF_SECURITY_APP_ID` | Security Cloud API username |
| `JAMF_SECURITY_APP_SECRET` | Security Cloud API password |

---

## Tool Filtering (Optional)

You can limit the registered tools to specific types using the `JAMF_TOOL_FILTER` environment variable or the `--tool-filter` command-line argument. This is useful if you want to restrict the LLM to only use "safe" high-level workflows or conversely, give it full raw API access.

| Value | Description |
|-------|-------------|
| `all` | (Default) Registers **all** available tools. |
| `api` | Registers only **direct API primitives** (1:1 with Jamf Pro API). Useful for power users who want raw access. |
| `complex` | Registers only **complex usage workflows** (combinations of API calls). Useful for simpler, safer interaction. |

### Configuration Examples

#### Using Environment Variable
Add to your client configuration's `env` section:
```json
"env": {
  "JAMF_PRO_URL": "...",
  "JAMF_TOOL_FILTER": "api"
}
```

#### Using Command Line Argument
Update your client configuration's `args`:
```json
"args": ["run", "--directory", "/path/to/mcp-hub", "jamf-mcp", "--tool-filter=complex"]
```

---

## Product Filtering (Optional)

You can limit which tools are registered based on the product they belong to using the `--products` command-line argument or `JAMF_PRODUCTS` environment variable. This is useful if you only want to expose tools for specific products (e.g., only Jamf Pro tools).

**Available Products:**
- `jamf_pro` (alias: `pro`): Jamf Pro device management tools.
- `jamf_protect` (alias: `protect`): Jamf Protect endpoint security tools.
- `jamf_security_cloud` (alias: `security`, `risk`): Jamf Security Cloud risk tools.

> **Note:** Setup tools (`jamf_get_setup_status`, `jamf_configure_help`) are always registered regardless of filters.

### Usage Examples

#### Using Command Line Argument
Pass a space-separated list of products:
```bash
# Only Jamf Pro tools
uv run jamf-mcp --products pro

# Pro and Protect tools
uv run jamf-mcp --products pro protect
```

In your client configuration:
```json
"args": ["run", "--directory", "/path/to/mcp-hub", "jamf-mcp", "--products", "pro", "protect"]
```

#### Using Environment Variable
Set a comma-separated list of products:
```bash
export JAMF_PRODUCTS="pro,protect"
```

---

## Setting Up API Credentials in Jamf Pro

> **Tip:** The [automated setup script](#automated-setup-recommended) handles these steps for you. The manual steps below are provided as reference.

1. Log in to Jamf Pro
2. Navigate to **Settings > System > API Roles and Clients**
3. **Create an API Role** with permissions:

   | Resource | Permissions |
   |----------|-------------|
   | Computers | Read, Update |
   | Mobile Devices | Read, Update |
   | Users | Read, Update |
   | Smart/Static Computer Groups | Read, Create |
   | Smart/Static Mobile Device Groups | Read, Create |
   | Policies, Configuration Profiles, Scripts | Read |
   | Extension Attributes, Categories | Read, Create |

4. **Create an API Client** and assign the role
5. Copy the **Client ID** and generate a **Client Secret**

---

## Client Configuration

### Claude Desktop (macOS)

Config file: `~/Library/Application Support/Claude/claude_desktop_config.json`

#### Jamf Pro Only

```json
{
  "mcpServers": {
    "jamf": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mcp-hub", "jamf-mcp"],
      "env": {
        "JAMF_PRO_URL": "https://yourcompany.jamfcloud.com",
        "JAMF_PRO_CLIENT_ID": "your-client-id",
        "JAMF_PRO_CLIENT_SECRET": "your-client-secret"
      }
    }
  }
}
```

#### All Products (Pro + Protect + Security Cloud)

```json
{
  "mcpServers": {
    "jamf": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mcp-hub", "jamf-mcp"],
      "env": {
        "JAMF_PRO_URL": "https://yourcompany.jamfcloud.com",
        "JAMF_PRO_CLIENT_ID": "your-pro-client-id",
        "JAMF_PRO_CLIENT_SECRET": "your-pro-client-secret",
        "JAMF_PROTECT_URL": "https://yourorg.protect.jamfcloud.com/graphql",
        "JAMF_PROTECT_CLIENT_ID": "your-protect-client-id",
        "JAMF_PROTECT_PASSWORD": "your-protect-password",
        "JAMF_SECURITY_URL": "https://radar.wandera.com",
        "JAMF_SECURITY_APP_ID": "your-security-app-id",
        "JAMF_SECURITY_APP_SECRET": "your-security-secret"
      }
    }
  }
}
```

#### Using venv (instead of uv)

```json
{
  "mcpServers": {
    "jamf": {
      "command": "/path/to/mcp-hub/venv/bin/python",
      "args": ["-m", "jamf_mcp.server"],
      "env": {
        "JAMF_PRO_URL": "https://yourcompany.jamfcloud.com",
        "JAMF_PRO_CLIENT_ID": "your-client-id",
        "JAMF_PRO_CLIENT_SECRET": "your-client-secret"
      }
    }
  }
}
```

#### Using System Python

```json
{
  "mcpServers": {
    "jamf": {
      "command": "/opt/homebrew/bin/python3",
      "args": ["-m", "jamf_mcp.server"],
      "env": {
        "JAMF_PRO_URL": "https://yourcompany.jamfcloud.com",
        "JAMF_PRO_CLIENT_ID": "your-client-id",
        "JAMF_PRO_CLIENT_SECRET": "your-client-secret"
      }
    }
  }
}
```

Common macOS Python paths:
- `/opt/homebrew/bin/python3` — Homebrew (Apple Silicon)
- `/usr/local/bin/python3` — Homebrew (Intel)
- `/usr/bin/python3` — System Python

---

### Claude Desktop (Windows)

Config file: `%APPDATA%\Claude\claude_desktop_config.json`

#### Jamf Pro Only

```json
{
  "mcpServers": {
    "jamf": {
      "command": "uv",
      "args": ["run", "--directory", "C:\\path\\to\\mcp-hub", "jamf-mcp"],
      "env": {
        "JAMF_PRO_URL": "https://yourcompany.jamfcloud.com",
        "JAMF_PRO_CLIENT_ID": "your-client-id",
        "JAMF_PRO_CLIENT_SECRET": "your-client-secret"
      }
    }
  }
}
```

#### All Products (Pro + Protect + Security Cloud)

```json
{
  "mcpServers": {
    "jamf": {
      "command": "uv",
      "args": ["run", "--directory", "C:\\path\\to\\mcp-hub", "jamf-mcp"],
      "env": {
        "JAMF_PRO_URL": "https://yourcompany.jamfcloud.com",
        "JAMF_PRO_CLIENT_ID": "your-pro-client-id",
        "JAMF_PRO_CLIENT_SECRET": "your-pro-client-secret",
        "JAMF_PROTECT_URL": "https://yourorg.protect.jamfcloud.com/graphql",
        "JAMF_PROTECT_CLIENT_ID": "your-protect-client-id",
        "JAMF_PROTECT_PASSWORD": "your-protect-password",
        "JAMF_SECURITY_URL": "https://radar.wandera.com",
        "JAMF_SECURITY_APP_ID": "your-security-app-id",
        "JAMF_SECURITY_APP_SECRET": "your-security-secret"
      }
    }
  }
}
```

#### Using venv (instead of uv)

```json
{
  "mcpServers": {
    "jamf": {
      "command": "C:\\path\\to\\mcp-hub\\venv\\Scripts\\python.exe",
      "args": ["-m", "jamf_mcp.server"],
      "env": {
        "JAMF_PRO_URL": "https://yourcompany.jamfcloud.com",
        "JAMF_PRO_CLIENT_ID": "your-client-id",
        "JAMF_PRO_CLIENT_SECRET": "your-client-secret"
      }
    }
  }
}
```

---

### Claude Code CLI

Set environment variables in your shell profile (`.zshrc`, `.bashrc`, etc.):

```bash
# Required: Jamf Pro
export JAMF_PRO_URL="https://yourcompany.jamfcloud.com"
export JAMF_PRO_CLIENT_ID="your-client-id"
export JAMF_PRO_CLIENT_SECRET="your-client-secret"

# Optional: Jamf Protect
export JAMF_PROTECT_URL="https://yourorg.protect.jamfcloud.com/graphql"
export JAMF_PROTECT_CLIENT_ID="your-protect-client-id"
export JAMF_PROTECT_PASSWORD="your-protect-password"

# Optional: Jamf Security Cloud
export JAMF_SECURITY_URL="https://radar.wandera.com"
export JAMF_SECURITY_APP_ID="your-security-app-id"
export JAMF_SECURITY_APP_SECRET="your-security-secret"
```

Add to your `.mcp.json` or Claude Code settings:

```json
{
  "mcpServers": {
    "jamf": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mcp-hub", "jamf-mcp"]
    }
  }
}
```

> **Note:** When using shell profile exports, you don't need to repeat the env vars in `.mcp.json`.

---

### Other MCP Clients

Any MCP-compatible client can connect to this server. Configure it similarly to Claude Desktop — specify the command (`uv` or `python`), args, and environment variables. The server communicates via stdio using the MCP protocol.

#### Testing Your Configuration

Use these commands to verify the server works before configuring a client:

```bash
# Quick test with inline env vars (Jamf Pro only)
JAMF_PRO_URL=https://yourcompany.jamfcloud.com \
JAMF_PRO_CLIENT_ID=your-id \
JAMF_PRO_CLIENT_SECRET=your-secret \
uv run --directory /path/to/mcp-hub jamf-mcp
```

#### MCP Protocol Test

Send an initialize request to verify the server responds correctly:

```bash
echo '{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"capabilities": {}, "clientInfo": {"name": "test"}, "protocolVersion": "2024-11-05"}}' | \
  JAMF_PRO_URL=https://yourcompany.jamfcloud.com \
  JAMF_PRO_CLIENT_ID=your-id \
  JAMF_PRO_CLIENT_SECRET=your-secret \
  uv run jamf-mcp
```

---

## Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| `401 Unauthorized` | Invalid credentials | Verify `JAMF_PRO_CLIENT_ID` and `JAMF_PRO_CLIENT_SECRET` |
| `403 Forbidden` | Insufficient permissions | Add required permissions to API role in Jamf Pro |
| `404 Not Found` | Wrong URL | Verify `JAMF_PRO_URL` is correct |
| Connection timeout | Network issue | Check firewall rules, verify server accessibility |
| `JAMF_PRO_URL required` | Missing env var | Ensure environment variables are set |
| Protect tools fail | Missing config | Set `JAMF_PROTECT_*` environment variables |
| Risk tools fail | Missing config | Set `JAMF_SECURITY_*` environment variables |

### Finding Your Python Path

```bash
# macOS/Linux
which python3

# Windows (PowerShell)
Get-Command python | Select-Object Source
```

### Verifying Installation

```bash
# Check if package is installed
python3 -c "import jamf_mcp; print(jamf_mcp.__version__)"

# Test MCP server starts
uv run jamf-mcp --help
```
