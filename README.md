![icon.png](assets/icon.png)

# Jamf MCP Server

An MCP server that enables LLMs to interact with Jamf Pro, Protect, and Security Cloud for Apple device management.

## Quick Start

### Automated Setup (Recommended)

The setup script creates API credentials in Jamf Pro and configures Claude Desktop automatically:

```bash
cd /path/to/mcp-hub
bash setup.sh
```

The script will:
1. Prompt for your Jamf Pro URL and admin credentials
2. Create an API Role and Integration with the right privileges
3. Generate client credentials (ID + secret)
4. Write the Claude Desktop config file for you

After setup, restart Claude Desktop and you're ready to go.

### Manual Setup

1. **Configure your MCP client** (see [Installation](docs/INSTALLATION.md))
2. **Restart your client** — it automatically starts the server
3. **Ask Claude** for help:
   - "What's the setup status?" → shows which products are configured
   - "How do I configure Jamf Pro?" → step-by-step setup instructions

No credentials required to start — the server runs in onboarding mode until configured.

### Try It Out

Once configured, ask things like:

- "Find all computers running macOS 15"
- "Create a smart group for M3 MacBooks"
- "Show me policies in the Security category"

See [Installation](docs/INSTALLATION.md) for full configuration details.

## Documentation

| Doc                                  | Description                                                 |
| ------------------------------------ | ----------------------------------------------------------- |
| [Installation](docs/INSTALLATION.md) | Setup, env vars, client configuration (Claude Desktop, CLI) |
| [Tools](docs/TOOLS.md)               | Complete reference for all 45 MCP tools by product          |
| [Contributing](CONTRIBUTING.md)      | Development setup, testing, adding new tools                |

## Supported Products

| Product                 | Tools | Description                                                      |
| ----------------------- | ----- | ---------------------------------------------------------------- |
| **Setup**               | 2     | Onboarding tools (always available, no credentials needed)       |
| **Jamf Pro**            | 37    | Device management, groups, policies, profiles, apps, scripts     |
| **Jamf Protect**        | 6     | Security alerts, enrolled computers, analytics (detection rules) |
| **Jamf Security Cloud** | 2     | Device risk status and overrides via RISK API                    |

## Requirements

- Python 3.10+
- Jamf instance (optional - server starts without credentials for onboarding)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, testing, and guidelines.

## License

MIT — See [LICENSE](LICENSE)

## Links

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Jamf Developer Portal](https://developer.jamf.com/)
