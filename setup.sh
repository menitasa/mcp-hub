#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# setup.sh — Automated setup for Jamf MCP Server
#
# Creates an API Role + Integration in Jamf Pro with the appropriate
# privileges, generates client credentials, and writes the Claude Desktop
# configuration file.
#
# Usage: ./setup.sh
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROLE_NAME="Jamf MCP Role"
INTEGRATION_NAME="Jamf MCP Integration"
readonly CLAUDE_CONFIG_DIR="$HOME/Library/Application Support/Claude"
readonly CLAUDE_CONFIG="${CLAUDE_CONFIG_DIR}/claude_desktop_config.json"

# ─── State (cleared on exit) ────────────────────────────────────────────────

JAMF_URL=""
BEARER_TOKEN=""
ADMIN_USER=""
ADMIN_PASS=""
CREATED_ROLE_ID=""
CREATED_INTEGRATION_ID=""
CLIENT_ID=""
CLIENT_SECRET=""
PRIVS_TMPFILE=""
ALL_PRIVS_FILE=""
SELECTED_PRIVS_FILE=""

# ─── Colors ──────────────────────────────────────────────────────────────────

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; CYAN='\033[0;36m'; BOLD='\033[1m'
DIM='\033[2m'; NC='\033[0m'

# ─── Output helpers ──────────────────────────────────────────────────────────

info()    { printf "  ${BLUE}▸${NC} %s\n" "$1"; }
success() { printf "  ${GREEN}✓${NC} %s\n" "$1"; }
warn()    { printf "  ${YELLOW}!${NC} %s\n" "$1" >&2; }
die()     { printf "\n  ${RED}✗${NC} %s\n\n" "$1" >&2; exit 1; }
step()    { printf "\n${BOLD}${CYAN}─── %s ───${NC}\n\n" "$1"; }

# ─── JSON helpers (no jq / no python) ────────────────────────────────────────

# Extract a simple top-level string value from JSON.
# Usage: json_val '{"key":"val"}' key
json_val() {
    local json="$1" key="$2"
    local result
    # Match "key": "value" (string)
    result=$(printf '%s' "$json" | sed -n 's/.*"'"$key"'"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
    if [[ -n "$result" ]]; then
        printf '%s' "$result"
        return
    fi
    # Match "key": number/bool/null
    result=$(printf '%s' "$json" | sed -n 's/.*"'"$key"'"[[:space:]]*:[[:space:]]*\([^,}"[:space:]]*\).*/\1/p' | head -1)
    if [[ "$result" == "null" ]]; then
        printf ''
    else
        printf '%s' "$result"
    fi
}

# Extract a JSON array of strings, one per line to stdout.
# Usage: json_string_array '{"privileges":["a","b"]}' privileges
json_string_array() {
    local json="$1" key="$2"
    printf '%s' "$json" \
        | sed -n 's/.*"'"$key"'"[[:space:]]*:[[:space:]]*\[/\[/p' \
        | sed 's/\].*/]/' \
        | grep -o '"[^"]*"' \
        | sed 's/^"//;s/"$//'
}

# Escape a string for safe JSON embedding.
json_escape() {
    local str="$1"
    str="${str//\\/\\\\}"
    str="${str//\"/\\\"}"
    printf '%s' "$str"
}

# ─── Cleanup trap ────────────────────────────────────────────────────────────

cleanup() {
    local ec=$?

    # Invalidate bearer token if we have one
    if [[ -n "${BEARER_TOKEN}" && -n "${JAMF_URL}" ]]; then
        curl -s -X POST "${JAMF_URL}/api/v1/auth/invalidate-token" \
            -H "Authorization: Bearer ${BEARER_TOKEN}" >/dev/null 2>&1 || true
    fi

    # Remove temp files
    [[ -n "${PRIVS_TMPFILE}" && -f "${PRIVS_TMPFILE}" ]] && rm -f "${PRIVS_TMPFILE}"
    [[ -n "${ALL_PRIVS_FILE}" && -f "${ALL_PRIVS_FILE}" ]] && rm -f "${ALL_PRIVS_FILE}"
    [[ -n "${SELECTED_PRIVS_FILE}" && -f "${SELECTED_PRIVS_FILE}" ]] && rm -f "${SELECTED_PRIVS_FILE}"

    # Wipe secrets from memory
    BEARER_TOKEN=""
    ADMIN_USER=""
    ADMIN_PASS=""
    CLIENT_SECRET=""

    # Report partially-created resources on failure
    if [[ $ec -ne 0 && ( -n "${CREATED_ROLE_ID}" || -n "${CREATED_INTEGRATION_ID}" ) ]]; then
        echo ""
        warn "Setup did not complete. You may need to clean up manually:"
        warn "Jamf Pro → Settings → API Roles and Clients"
        [[ -n "${CREATED_ROLE_ID}" ]]        && warn "  • API Role '${ROLE_NAME}' (ID: ${CREATED_ROLE_ID})"
        [[ -n "${CREATED_INTEGRATION_ID}" ]] && warn "  • API Integration '${INTEGRATION_NAME}' (ID: ${CREATED_INTEGRATION_ID})"
        echo ""
    fi
}
trap cleanup EXIT

# ─── Banner ──────────────────────────────────────────────────────────────────

banner() {
    clear
    echo ""
    printf "${BOLD}"
    cat << 'BANNER'

      Automated Setup for Claude Desktop
      
BANNER
    printf "${NC}\n"
}

# ─── Dependency checks ──────────────────────────────────────────────────────

check_deps() {
    step "Checking dependencies"
    local ok=1
    for cmd in curl uv; do
        if command -v "$cmd" >/dev/null 2>&1; then
            success "$cmd found"
        else
            warn "$cmd not found"
            ok=0
        fi
    done

    if [[ ! -f "${SCRIPT_DIR}/pyproject.toml" ]]; then
        die "pyproject.toml not found in ${SCRIPT_DIR}. Run this script from the project root."
    fi
    success "pyproject.toml found"

    if [[ $ok -eq 0 ]]; then
        echo ""
        command -v uv >/dev/null 2>&1 || info "Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
        die "Install missing dependencies and try again."
    fi
}

# ─── Collect Jamf Pro URL and admin credentials ─────────────────────────────

collect_credentials() {
    step "Jamf Pro Connection"

    read -r -p "  Jamf Pro URL (e.g. https://company.jamfcloud.com): " JAMF_URL
    JAMF_URL="${JAMF_URL%/}"  # strip trailing slash

    if [[ ! "${JAMF_URL}" =~ ^https:// ]]; then
        die "URL must start with https://"
    fi

    echo ""
    read -r -p "  Admin username: " ADMIN_USER
    read -rs -p "  Admin password: " ADMIN_PASS
    echo ""  # newline after hidden input

    if [[ -z "${ADMIN_USER}" || -z "${ADMIN_PASS}" ]]; then
        die "Username and password are required."
    fi
}

# ─── Authenticate with Basic Auth → bearer token ────────────────────────────

authenticate() {
    step "Authenticating"

    info "Requesting bearer token from ${JAMF_URL}..."

    local basic_auth
    basic_auth=$(printf '%s:%s' "${ADMIN_USER}" "${ADMIN_PASS}" | base64 | tr -d '\n')

    # Clear admin credentials immediately
    ADMIN_USER=""
    ADMIN_PASS=""

    local response http_code body
    response=$(curl -s -w "\n%{http_code}" -X POST "${JAMF_URL}/api/v1/auth/token" \
        -H "Authorization: Basic ${basic_auth}" \
        -H "Accept: application/json") || die "Network error — cannot reach ${JAMF_URL}"

    basic_auth=""

    http_code=$(echo "$response" | tail -1)
    body=$(echo "$response" | sed '$ d')

    if [[ "${http_code}" != "200" ]]; then
        case "${http_code}" in
            401) die "Authentication failed — check your username and password." ;;
            *)   die "Authentication failed (HTTP ${http_code}). Response: ${body}" ;;
        esac
    fi

    BEARER_TOKEN=$(json_val "${body}" "token")
    if [[ -z "${BEARER_TOKEN}" ]]; then
        die "No token in authentication response."
    fi

    success "Authenticated successfully"
}

# ─── API call helpers ─────────────────────────────────────────────────────────

RESP_CODE=""
RESP_BODY=""

# Make an authenticated API call. Sets RESP_CODE and RESP_BODY.
api() {
    local method="$1" endpoint="$2" data="${3:-}"
    local url="${JAMF_URL}${endpoint}"

    local response
    if [[ -n "${data}" ]]; then
        response=$(curl -s -w "\n%{http_code}" -X "${method}" "${url}" \
            -H "Authorization: Bearer ${BEARER_TOKEN}" \
            -H "Accept: application/json" \
            -H "Content-Type: application/json" \
            -d "${data}") || die "Network error during API call to ${endpoint}"
    else
        response=$(curl -s -w "\n%{http_code}" -X "${method}" "${url}" \
            -H "Authorization: Bearer ${BEARER_TOKEN}" \
            -H "Accept: application/json") || die "Network error during API call to ${endpoint}"
    fi

    RESP_CODE=$(echo "$response" | tail -1)
    RESP_BODY=$(echo "$response" | sed '$ d')
}

# ─── Fetch available privileges from the API ─────────────────────────────────

fetch_privileges() {
    step "Fetching available privileges"

    api GET "/api/v1/api-role-privileges"

    if [[ "${RESP_CODE}" != "200" ]]; then
        die "Failed to fetch privileges (HTTP ${RESP_CODE}): ${RESP_BODY}"
    fi

    PRIVS_TMPFILE=$(mktemp)
    echo "${RESP_BODY}" > "${PRIVS_TMPFILE}"

    # Write all privileges to a temp file (one per line)
    ALL_PRIVS_FILE=$(mktemp)
    json_string_array "${RESP_BODY}" "privileges" > "${ALL_PRIVS_FILE}"

    local count
    count=$(wc -l < "${ALL_PRIVS_FILE}" | tr -d ' ')

    success "Found ${count} available privileges"
}

# ─── Privilege selection ─────────────────────────────────────────────────────

# Check if a string contains a substring.
string_contains() {
    case "$1" in
        *"$2"*) return 0 ;;
        *)      return 1 ;;
    esac
}

# Match privileges for a category. Writes matches to stdout.
# Usage: match_category "include1,include2" "exclude1,exclude2" < privs_file
match_category() {
    local includes_str="$1" excludes_str="$2"

    while IFS= read -r priv; do
        [[ -z "$priv" ]] && continue

        # Check includes
        local matched=0
        local oldIFS="$IFS"
        IFS=','
        for inc in $includes_str; do
            IFS="$oldIFS"
            if string_contains "$priv" "$inc"; then
                matched=1
                break
            fi
            IFS=','
        done
        IFS="$oldIFS"
        [[ $matched -eq 0 ]] && continue

        # Check excludes
        local excluded=0
        if [[ -n "$excludes_str" ]]; then
            IFS=','
            for exc in $excludes_str; do
                IFS="$oldIFS"
                [[ -z "$exc" ]] && continue
                if string_contains "$priv" "$exc"; then
                    excluded=1
                    break
                fi
                IFS=','
            done
            IFS="$oldIFS"
        fi
        [[ $excluded -eq 1 ]] && continue

        echo "$priv"
    done
}

select_privileges() {
    step "Privilege Selection"

    echo "  Choose which tool categories to enable:"
    echo ""
    printf "    ${BOLD}1)${NC} All Tools — enable all available privileges (recommended)\n"
    printf "    ${BOLD}2)${NC} Granular  — pick categories individually\n"
    echo ""
    read -r -p "  Selection [1]: " choice
    choice="${choice:-1}"

    SELECTED_PRIVS_FILE=$(mktemp)

    if [[ "${choice}" == "1" ]]; then
        cp "${ALL_PRIVS_FILE}" "${SELECTED_PRIVS_FILE}"
        local total
        total=$(wc -l < "${SELECTED_PRIVS_FILE}" | tr -d ' ')
        echo ""
        success "All privileges enabled (${total} total)"
        return
    fi

    echo ""
    info "Press Enter or Y for each category to include, N to skip."
    echo ""

    # Track which privs have been categorized
    local used_file
    used_file=$(mktemp)
    : > "${used_file}"

    # Category definitions: name|includes|excludes
    local cat_name includes_str excludes_str
    while IFS='|' read -r cat_name includes_str excludes_str; do
        # Find matching privileges
        local cat_file
        cat_file=$(mktemp)
        match_category "$includes_str" "$excludes_str" < "${ALL_PRIVS_FILE}" > "$cat_file"

        local cat_count
        cat_count=$(wc -l < "$cat_file" | tr -d ' ')

        if [[ $cat_count -gt 0 ]]; then
            # Record these as used
            cat "$cat_file" >> "$used_file"

            local answer
            read -r -p "  $(printf '%-34s' "$cat_name ($cat_count privs)") [Y/n] " answer
            if [[ -z "$answer" || "$answer" == [Yy]* ]]; then
                cat "$cat_file" >> "$SELECTED_PRIVS_FILE"
            fi
        fi

        rm -f "$cat_file"
    done <<EOF
Computers|Computer|Group,Extension,PreStage,Prestage,Configuration
Mobile Devices|Mobile Device|Group,Extension,PreStage,Prestage,Configuration,Application
Users|User|Extension,Group
Groups|Group|
Policies|Polic|Patch
Configuration Profiles|Configuration Profile|
Scripts|Script|
App Installers|App Installer|
Extension Attributes|Extension Attribute|
Categories|Categor|
Buildings & Departments|Building,Department|
PreStage Enrollments|PreStage,Prestage|
Apps & Content|Mac App,Mobile Device App,eBook,Patch,Restricted Software,VPP|App Installer
Printers|Printer|
API Roles & Integrations|API Role,API Integration|
EOF

    # Collect uncategorized privileges into "Other"
    local other_file
    other_file=$(mktemp)
    while IFS= read -r priv; do
        [[ -z "$priv" ]] && continue
        if ! grep -qxF "$priv" "$used_file"; then
            echo "$priv" >> "$other_file"
        fi
    done < "${ALL_PRIVS_FILE}"

    local other_count
    other_count=$(wc -l < "$other_file" | tr -d ' ')

    if [[ $other_count -gt 0 ]]; then
        local answer
        read -r -p "  $(printf '%-34s' "Other ($other_count privs)") [Y/n] " answer
        if [[ -z "$answer" || "$answer" == [Yy]* ]]; then
            cat "$other_file" >> "$SELECTED_PRIVS_FILE"
        fi
    fi

    rm -f "$used_file" "$other_file"

    echo ""
    local total
    total=$(wc -l < "$SELECTED_PRIVS_FILE" | tr -d ' ')
    if [[ $total -eq 0 ]]; then
        die "No categories selected. At least one category is required."
    fi
    success "${total} privileges selected"
}

# ─── Create API Role ─────────────────────────────────────────────────────────

create_role() {
    step "Creating API Role"

    # Build the privileges JSON array
    local privs_json=""
    while IFS= read -r priv; do
        [[ -z "$priv" ]] && continue
        [[ -n "$privs_json" ]] && privs_json+=","
        privs_json+="\"$(json_escape "$priv")\""
    done < "${SELECTED_PRIVS_FILE}"

    local role_name="${ROLE_NAME}"

    while true; do
        local payload
        payload=$(printf '{"displayName":"%s","privileges":[%s]}' \
            "$(json_escape "${role_name}")" \
            "${privs_json}")

        api POST "/api/v1/api-roles" "${payload}"

        if [[ "${RESP_CODE}" == "200" || "${RESP_CODE}" == "201" ]]; then
            break
        fi

        # Check if this is a duplicate name error
        if [[ "${RESP_CODE}" == "400" ]] && string_contains "${RESP_BODY}" "must be unique"; then
            warn "'${role_name}' already exists in Jamf Pro."
            echo ""
            printf "    ${BOLD}1)${NC} Auto-rename to next available (e.g. ${role_name} 2)\n"
            printf "    ${BOLD}2)${NC} Enter a custom name\n"
            printf "    ${BOLD}3)${NC} Cancel setup\n"
            echo ""
            read -r -p "  Selection [1]: " name_choice
            name_choice="${name_choice:-1}"

            case "${name_choice}" in
                1)
                    # Auto-increment: try "Name 2", "Name 3", etc.
                    local i=2
                    local base_name="${ROLE_NAME}"
                    role_name="${base_name} ${i}"
                    info "Trying '${role_name}'..."
                    ;;
                2)
                    read -r -p "  New role name: " role_name
                    if [[ -z "$role_name" ]]; then
                        die "Role name cannot be empty."
                    fi
                    info "Trying '${role_name}'..."
                    ;;
                *)
                    die "Setup cancelled."
                    ;;
            esac

            # For auto-increment, keep bumping the number if still duplicate
            if [[ "${name_choice}" == "1" ]]; then
                while true; do
                    payload=$(printf '{"displayName":"%s","privileges":[%s]}' \
                        "$(json_escape "${role_name}")" \
                        "${privs_json}")

                    api POST "/api/v1/api-roles" "${payload}"

                    if [[ "${RESP_CODE}" == "200" || "${RESP_CODE}" == "201" ]]; then
                        break 2
                    fi

                    if [[ "${RESP_CODE}" == "400" ]] && string_contains "${RESP_BODY}" "must be unique"; then
                        i=$((i + 1))
                        role_name="${base_name} ${i}"
                        info "Trying '${role_name}'..."
                        if [[ $i -gt 50 ]]; then
                            die "Too many existing roles. Please clean up in Jamf Pro."
                        fi
                    else
                        die "Failed to create API Role (HTTP ${RESP_CODE}): ${RESP_BODY}"
                    fi
                done
            fi
            continue
        fi

        die "Failed to create API Role (HTTP ${RESP_CODE}): ${RESP_BODY}"
    done

    ROLE_NAME="${role_name}"
    CREATED_ROLE_ID=$(json_val "${RESP_BODY}" "id")
    success "Created API Role '${ROLE_NAME}' (ID: ${CREATED_ROLE_ID})"
}

# ─── Create API Integration ──────────────────────────────────────────────────

create_integration() {
    step "Creating API Integration"

    local integration_name="${INTEGRATION_NAME}"

    while true; do
        local payload
        payload=$(printf '{"displayName":"%s","authorizationScopes":["%s"],"enabled":true,"accessTokenLifetimeSeconds":1800}' \
            "$(json_escape "${integration_name}")" \
            "$(json_escape "${ROLE_NAME}")")

        api POST "/api/v1/api-integrations" "${payload}"

        if [[ "${RESP_CODE}" == "200" || "${RESP_CODE}" == "201" ]]; then
            break
        fi

        # Check if this is a duplicate name error
        if [[ "${RESP_CODE}" == "400" ]] && string_contains "${RESP_BODY}" "must be unique"; then
            warn "'${integration_name}' already exists in Jamf Pro."
            echo ""
            printf "    ${BOLD}1)${NC} Auto-rename to next available (e.g. ${integration_name} 2)\n"
            printf "    ${BOLD}2)${NC} Enter a custom name\n"
            printf "    ${BOLD}3)${NC} Cancel setup\n"
            echo ""
            read -r -p "  Selection [1]: " name_choice
            name_choice="${name_choice:-1}"

            case "${name_choice}" in
                1)
                    local i=2
                    local base_name="${INTEGRATION_NAME}"
                    integration_name="${base_name} ${i}"
                    info "Trying '${integration_name}'..."
                    ;;
                2)
                    read -r -p "  New integration name: " integration_name
                    if [[ -z "$integration_name" ]]; then
                        die "Integration name cannot be empty."
                    fi
                    info "Trying '${integration_name}'..."
                    ;;
                *)
                    die "Setup cancelled."
                    ;;
            esac

            # For auto-increment, keep bumping the number if still duplicate
            if [[ "${name_choice}" == "1" ]]; then
                while true; do
                    payload=$(printf '{"displayName":"%s","authorizationScopes":["%s"],"enabled":true,"accessTokenLifetimeSeconds":1800}' \
                        "$(json_escape "${integration_name}")" \
                        "$(json_escape "${ROLE_NAME}")")

                    api POST "/api/v1/api-integrations" "${payload}"

                    if [[ "${RESP_CODE}" == "200" || "${RESP_CODE}" == "201" ]]; then
                        break 2
                    fi

                    if [[ "${RESP_CODE}" == "400" ]] && string_contains "${RESP_BODY}" "must be unique"; then
                        i=$((i + 1))
                        integration_name="${base_name} ${i}"
                        info "Trying '${integration_name}'..."
                        if [[ $i -gt 50 ]]; then
                            die "Too many existing integrations. Please clean up in Jamf Pro."
                        fi
                    else
                        die "Failed to create API Integration (HTTP ${RESP_CODE}): ${RESP_BODY}"
                    fi
                done
            fi
            continue
        fi

        die "Failed to create API Integration (HTTP ${RESP_CODE}): ${RESP_BODY}"
    done

    INTEGRATION_NAME="${integration_name}"
    CREATED_INTEGRATION_ID=$(json_val "${RESP_BODY}" "id")
    success "Created API Integration '${INTEGRATION_NAME}' (ID: ${CREATED_INTEGRATION_ID})"
}

# ─── Generate Client Credentials ─────────────────────────────────────────────

generate_credentials() {
    step "Generating Client Credentials"

    api POST "/api/v1/api-integrations/${CREATED_INTEGRATION_ID}/client-credentials" "{}"

    if [[ "${RESP_CODE}" != "200" && "${RESP_CODE}" != "201" ]]; then
        die "Failed to generate credentials (HTTP ${RESP_CODE}): ${RESP_BODY}"
    fi

    CLIENT_ID=$(json_val "${RESP_BODY}" "clientId")
    CLIENT_SECRET=$(json_val "${RESP_BODY}" "clientSecret")

    if [[ -z "${CLIENT_ID}" || -z "${CLIENT_SECRET}" ]]; then
        die "Credentials response missing clientId or clientSecret."
    fi

    success "Client credentials generated"
}

# ─── Write / merge Claude Desktop config ─────────────────────────────────────

# Extract top-level server names from mcpServers using brace-depth tracking.
# Outputs one server name per line.
_list_mcp_servers() {
    local file="$1"
    awk '
    BEGIN { in_mcp=0; depth=0 }
    /"mcpServers"[[:space:]]*:/ {
        in_mcp=1
        n=split($0,c,"")
        for(i=1;i<=n;i++) {
            if(c[i]=="{") depth++
            if(c[i]=="}") depth--
        }
        next
    }
    in_mcp {
        # Count braces before checking for keys
        prev_depth=depth
        n=split($0,c,"")
        for(i=1;i<=n;i++) {
            if(c[i]=="{") depth++
            if(c[i]=="}") depth--
        }
        # At depth 2 (inside mcpServers obj), a quoted key is a server name
        # We detect it when prev_depth was 1 (just entered) or depth is >= 2
        if(prev_depth==1 && match($0, /^[[:space:]]*"[^"]+"[[:space:]]*:/)) {
            line=$0
            gsub(/^[[:space:]]*"/, "", line)
            gsub(/".*/, "", line)
            print line
        }
        if(depth<=0) in_mcp=0
    }
    ' "$file" 2>/dev/null
}

# Find any MCP server entry whose key or content contains "jamf-mcp".
# Also matches a key named exactly "jamf".
# Outputs matching key names, one per line.
_find_jamf_entries() {
    local file="$1"
    awk '
    BEGIN { in_mcp=0; mcp_depth=0; in_server=0; server_depth=0; server_name=""; has_jamf_mcp=0 }
    /"mcpServers"[[:space:]]*:/ {
        in_mcp=1
        n=split($0,c,"")
        for(i=1;i<=n;i++) { if(c[i]=="{") mcp_depth++; if(c[i]=="}") mcp_depth-- }
        next
    }
    in_mcp {
        prev_depth=mcp_depth
        n=split($0,c,"")
        for(i=1;i<=n;i++) { if(c[i]=="{") mcp_depth++; if(c[i]=="}") mcp_depth-- }

        # Detect start of a server entry
        if(!in_server && prev_depth==1 && match($0, /^[[:space:]]*"[^"]+"[[:space:]]*:/)) {
            line=$0
            gsub(/^[[:space:]]*"/, "", line)
            gsub(/".*/, "", line)
            server_name=line
            in_server=1
            server_depth=mcp_depth
            has_jamf_mcp=0
            if(index($0, "jamf-mcp") || server_name == "jamf") has_jamf_mcp=1
            next
        }

        if(in_server) {
            if(index($0, "jamf-mcp")) has_jamf_mcp=1
            if(mcp_depth < server_depth || mcp_depth <= 1) {
                if(has_jamf_mcp) print server_name
                in_server=0
            }
        }

        if(mcp_depth<=0) {
            if(in_server && has_jamf_mcp) print server_name
            in_mcp=0; in_server=0
        }
    }
    ' "$file" 2>/dev/null
}

# Remove a JSON block for a given key from mcpServers.
# Handles nested braces. Writes result to stdout.
_remove_mcp_entry() {
    local file="$1" key="$2"
    awk -v key="\"${key}\"" '
    BEGIN { skip=0; depth=0 }
    {
        if (!skip && index($0, key) && index($0, ":")) {
            skip=1; depth=0
            n = split($0, chars, "")
            for (i=1; i<=n; i++) {
                if (chars[i] == "{") depth++
                if (chars[i] == "}") depth--
            }
            if (depth <= 0) skip=0
            next
        }
        if (skip) {
            n = split($0, chars, "")
            for (i=1; i<=n; i++) {
                if (chars[i] == "{") depth++
                if (chars[i] == "}") depth--
            }
            if (depth <= 0) skip=0
            next
        }
        print
    }' "$file"
}

write_claude_config() {
    step "Configuring Claude Desktop"

    mkdir -p "${CLAUDE_CONFIG_DIR}"

    # Build the jamf entry as compact single-line JSON for safe sed insertion
    local jamf_entry
    jamf_entry=$(printf '"jamf": { "command": "uv", "args": ["run", "--directory", "%s", "jamf-mcp"], "env": { "JAMF_PRO_URL": "%s", "JAMF_PRO_CLIENT_ID": "%s", "JAMF_PRO_CLIENT_SECRET": "%s" } }' \
        "$(json_escape "${SCRIPT_DIR}")" \
        "$(json_escape "${JAMF_URL}")" \
        "$(json_escape "${CLIENT_ID}")" \
        "$(json_escape "${CLIENT_SECRET}")")

    # ── Case 1: No config file exists → write fresh ──
    if [[ ! -f "${CLAUDE_CONFIG}" ]]; then
        printf '{\n  "mcpServers": {\n    %s\n  }\n}\n' "${jamf_entry}" > "${CLAUDE_CONFIG}"
        success "Claude Desktop config created"
        info "${CLAUDE_CONFIG}"
        return
    fi

    # ── Config file exists — inspect it ──
    local existing
    existing=$(cat "${CLAUDE_CONFIG}")

    # Check if file is empty or not valid JSON-ish
    if [[ -z "${existing}" ]] || ! printf '%s' "${existing}" | grep -q '{'; then
        warn "Existing config is empty or invalid."
        read -r -p "  Overwrite with new config? [Y/n] " answer
        if [[ -n "$answer" && "$answer" != [Yy]* ]]; then
            warn "Skipped. Add credentials manually:"
            info "JAMF_PRO_URL=${JAMF_URL}"
            info "JAMF_PRO_CLIENT_ID=${CLIENT_ID}"
            info "JAMF_PRO_CLIENT_SECRET=<generated — see Jamf Pro console>"
            return
        fi
        printf '{\n  "mcpServers": {\n    %s\n  }\n}\n' "${jamf_entry}" > "${CLAUDE_CONFIG}"
        success "Claude Desktop config created"
        info "${CLAUDE_CONFIG}"
        return
    fi

    # ── File has content — discover servers ──
    local has_mcp=0
    printf '%s' "${existing}" | grep -q '"mcpServers"' && has_mcp=1

    local server_names="" jamf_conflicts=""
    if [[ $has_mcp -eq 1 ]]; then
        server_names=$(_list_mcp_servers "${CLAUDE_CONFIG}")
        jamf_conflicts=$(_find_jamf_entries "${CLAUDE_CONFIG}")
    fi

    # Show existing servers
    if [[ -n "$server_names" ]]; then
        info "Existing MCP servers in config:"
        echo "$server_names" | while IFS= read -r name; do
            if [[ -n "$jamf_conflicts" ]] && echo "$jamf_conflicts" | grep -qxF "$name"; then
                printf "    • %s ${YELLOW}(uses jamf-mcp)${NC}\n" "$name"
            else
                printf "    • %s\n" "$name"
            fi
        done
        echo ""
    fi

    # ── Case 2: Existing entry conflicts (named "jamf" or references jamf-mcp) ──
    if [[ -n "$jamf_conflicts" ]]; then
        local conflict_count
        conflict_count=$(echo "$jamf_conflicts" | wc -l | tr -d ' ')
        local conflict_list
        conflict_list=$(echo "$jamf_conflicts" | sed 's/^/    • /')

        if [[ $conflict_count -eq 1 ]]; then
            local conflict_name
            conflict_name=$(echo "$jamf_conflicts" | head -1)
            warn "Found an existing entry that uses jamf-mcp: '${conflict_name}'"
        else
            warn "Found ${conflict_count} existing entries that use jamf-mcp:"
            echo "$conflict_list"
        fi
        echo ""
        printf "    ${BOLD}1)${NC} Replace conflicting entry/entries with new 'jamf' config\n"
        printf "    ${BOLD}2)${NC} Keep existing and add 'jamf' alongside them\n"
        printf "    ${BOLD}3)${NC} Skip config update\n"
        echo ""
        read -r -p "  Selection [1]: " conflict_choice
        conflict_choice="${conflict_choice:-1}"

        case "${conflict_choice}" in
            1)
                cp "${CLAUDE_CONFIG}" "${CLAUDE_CONFIG}.backup"
                # Remove each conflicting entry
                local tmp_current="${CLAUDE_CONFIG}"
                echo "$jamf_conflicts" | while IFS= read -r cname; do
                    local tmp
                    tmp=$(mktemp)
                    _remove_mcp_entry "$tmp_current" "$cname" > "$tmp"
                    cp "$tmp" "${CLAUDE_CONFIG}"
                    rm -f "$tmp"
                    tmp_current="${CLAUDE_CONFIG}"
                done

                # Insert new jamf entry
                local tmp
                tmp=$(mktemp)
                sed "/\"mcpServers\"/a\\
\\    ${jamf_entry}," "${CLAUDE_CONFIG}" > "$tmp"
                sed 's/,\([[:space:]]*}\)/\1/g' "$tmp" > "${CLAUDE_CONFIG}"
                rm -f "$tmp"

                success "Replaced conflicting entries, other servers preserved"
                info "${CLAUDE_CONFIG}"
                ;;
            2)
                cp "${CLAUDE_CONFIG}" "${CLAUDE_CONFIG}.backup"
                local tmp
                tmp=$(mktemp)
                sed "/\"mcpServers\"/a\\
\\    ${jamf_entry}," "${CLAUDE_CONFIG}" > "$tmp"
                sed 's/,\([[:space:]]*}\)/\1/g' "$tmp" > "${CLAUDE_CONFIG}"
                rm -f "$tmp"

                success "Added 'jamf' alongside existing entries"
                info "${CLAUDE_CONFIG}"
                ;;
            *)
                warn "Skipped. Add credentials manually:"
                info "JAMF_PRO_URL=${JAMF_URL}"
                info "JAMF_PRO_CLIENT_ID=${CLIENT_ID}"
                info "JAMF_PRO_CLIENT_SECRET=<generated — see Jamf Pro console>"
                ;;
        esac
        return
    fi

    # ── Case 3: Has mcpServers, no conflicts → append ──
    if [[ $has_mcp -eq 1 ]]; then
        read -r -p "  Append 'jamf' to existing MCP servers? [Y/n] " answer
        if [[ -n "$answer" && "$answer" != [Yy]* ]]; then
            warn "Skipped. Add credentials manually:"
            info "JAMF_PRO_URL=${JAMF_URL}"
            info "JAMF_PRO_CLIENT_ID=${CLIENT_ID}"
            info "JAMF_PRO_CLIENT_SECRET=<generated — see Jamf Pro console>"
            return
        fi

        cp "${CLAUDE_CONFIG}" "${CLAUDE_CONFIG}.backup"

        local tmp
        tmp=$(mktemp)
        sed "/\"mcpServers\"/a\\
\\    ${jamf_entry}," "${CLAUDE_CONFIG}" > "$tmp"
        sed 's/,\([[:space:]]*}\)/\1/g' "$tmp" > "${CLAUDE_CONFIG}"
        rm -f "$tmp"

        success "Appended 'jamf' to existing config"
        info "${CLAUDE_CONFIG}"
        return
    fi

    # ── Case 4: File has content but no mcpServers → ask to add it ──
    warn "Config exists but has no 'mcpServers' section."
    read -r -p "  Add mcpServers with jamf entry? [Y/n] " answer
    if [[ -n "$answer" && "$answer" != [Yy]* ]]; then
        warn "Skipped. Add credentials manually:"
        info "JAMF_PRO_URL=${JAMF_URL}"
        info "JAMF_PRO_CLIENT_ID=${CLIENT_ID}"
        info "JAMF_PRO_CLIENT_SECRET=<generated — see Jamf Pro console>"
        return
    fi

    cp "${CLAUDE_CONFIG}" "${CLAUDE_CONFIG}.backup"

    local tmp
    tmp=$(mktemp)
    sed "1,/{/ s/{/{ \"mcpServers\": { ${jamf_entry} },/" "${CLAUDE_CONFIG}" > "$tmp"
    mv "$tmp" "${CLAUDE_CONFIG}"

    success "Added mcpServers to existing config"
    info "${CLAUDE_CONFIG}"
}

# ─── Summary ─────────────────────────────────────────────────────────────────

print_summary() {
    step "Setup Complete"

    local priv_count
    priv_count=$(wc -l < "${SELECTED_PRIVS_FILE}" | tr -d ' ')

    printf "  ${BOLD}Jamf Pro URL:${NC}        %s\n" "${JAMF_URL}"
    printf "  ${BOLD}API Role:${NC}            %s (ID: %s)\n" "${ROLE_NAME}" "${CREATED_ROLE_ID}"
    printf "  ${BOLD}API Integration:${NC}     %s (ID: %s)\n" "${INTEGRATION_NAME}" "${CREATED_INTEGRATION_ID}"
    printf "  ${BOLD}Privileges:${NC}          %s\n" "${priv_count}"
    printf "  ${BOLD}Claude Config:${NC}       %s\n" "${CLAUDE_CONFIG}"
    echo ""
    info "Restart Claude Desktop to connect."
    info "Ask Claude: \"What's the setup status?\" to verify connectivity."
    echo ""
}

# ─── Main ─────────────────────────────────────────────────────────────────────

main() {
    banner
    check_deps
    collect_credentials
    authenticate
    fetch_privileges
    select_privileges
    create_role
    create_integration
    generate_credentials
    write_claude_config
    print_summary
}

main "$@"
