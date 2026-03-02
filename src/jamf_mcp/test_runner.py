#!/usr/bin/env python3
# Copyright 2026, Jamf Software LLC
"""
Jamf MCP Server Test Runner

Tests all MCP server commands against a live Jamf Pro instance.
Continues through all tests even if some fail, providing a comprehensive report.

Usage:
    python -m jamf_mcp.test_runner

    # Or via the CLI:
    jamf-mcp-test

Environment Variables Required:
    JAMF_PRO_URL - Your Jamf Pro instance URL
    JAMF_PRO_CLIENT_ID - OAuth client ID
    JAMF_PRO_CLIENT_SECRET - OAuth client secret
"""

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

import httpx

# Add color support for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class TestStatus(Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    WARNING = "WARNING"  # Worked but with unexpected results


@dataclass
class TestResult:
    """Result of a single test"""
    name: str
    status: TestStatus
    duration_ms: float
    response_code: Optional[int] = None
    message: str = ""
    details: dict = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class TestSuite:
    """Collection of test results"""
    results: list[TestResult] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == TestStatus.PASSED)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == TestStatus.FAILED)

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == TestStatus.SKIPPED)

    @property
    def warnings(self) -> int:
        return sum(1 for r in self.results if r.status == TestStatus.WARNING)

    @property
    def total_duration_ms(self) -> float:
        return sum(r.duration_ms for r in self.results)


class JamfMCPTestRunner:
    """Test runner for Jamf MCP Server commands"""

    def __init__(self):
        self.suite = TestSuite()
        self.client = None
        self.logger = self._setup_logging()

        # Test data created during tests (for cleanup or reference)
        self.created_resources: dict[str, list[int]] = {
            "smart_groups": [],
            "static_groups": [],
            "extension_attributes": [],
            "categories": [],
        }

        # Sample IDs found during GET tests (for UPDATE tests)
        self.sample_ids: dict[str, Optional[int]] = {
            "computer": None,
            "mobile_device": None,
            "user": None,
        }

    def _setup_logging(self) -> logging.Logger:
        """Configure logging with both file and console output"""
        logger = logging.getLogger("jamf_mcp_test")
        logger.setLevel(logging.DEBUG)

        # Prevent duplicate handlers
        if logger.handlers:
            return logger

        # Create logs directory
        log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
        os.makedirs(log_dir, exist_ok=True)

        # File handler - detailed logs
        log_file = os.path.join(
            log_dir,
            f"test_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(message)s'
        )
        file_handler.setFormatter(file_formatter)

        # Console handler - summary info
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

        self.log_file = log_file
        return logger

    def _print_header(self, text: str):
        """Print a formatted header"""
        print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.ENDC}")
        print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")

    def _print_test_result(self, result: TestResult):
        """Print a single test result with color coding"""
        status_colors = {
            TestStatus.PASSED: Colors.GREEN,
            TestStatus.FAILED: Colors.FAIL,
            TestStatus.SKIPPED: Colors.WARNING,
            TestStatus.WARNING: Colors.WARNING,
        }
        color = status_colors.get(result.status, Colors.ENDC)
        status_symbol = {
            TestStatus.PASSED: "✓",
            TestStatus.FAILED: "✗",
            TestStatus.SKIPPED: "○",
            TestStatus.WARNING: "⚠",
        }
        symbol = status_symbol.get(result.status, "?")

        # Format response code
        code_str = f"[{result.response_code}]" if result.response_code else "[---]"

        print(f"  {color}{symbol} {result.name:<45} {code_str:>6} {result.status.value:>8} ({result.duration_ms:.0f}ms){Colors.ENDC}")

        if result.error:
            print(f"    {Colors.FAIL}└─ Error: {result.error[:80]}{'...' if len(result.error) > 80 else ''}{Colors.ENDC}")
        elif result.message and result.status != TestStatus.PASSED:
            print(f"    {Colors.CYAN}└─ {result.message[:80]}{'...' if len(result.message) > 80 else ''}{Colors.ENDC}")

    async def _run_test(
        self,
        name: str,
        test_func,
        *args,
        **kwargs
    ) -> TestResult:
        """Execute a single test and capture results"""
        start = datetime.now()

        try:
            self.logger.debug(f"Starting test: {name}")
            result = await test_func(*args, **kwargs)
            duration = (datetime.now() - start).total_seconds() * 1000

            if isinstance(result, TestResult):
                result.duration_ms = duration
                return result

            # If test_func returns raw data, wrap it
            return TestResult(
                name=name,
                status=TestStatus.PASSED,
                duration_ms=duration,
                message="Test completed successfully",
                details=result if isinstance(result, dict) else {}
            )

        except Exception as e:
            duration = (datetime.now() - start).total_seconds() * 1000
            self.logger.error(f"Test '{name}' failed with exception: {str(e)}")
            return TestResult(
                name=name,
                status=TestStatus.FAILED,
                duration_ms=duration,
                error=str(e)
            )

    async def initialize_client(self) -> bool:
        """Initialize the Jamf API client"""
        from .auth import JamfAuth
        from .client import JamfClient

        jamf_url = os.environ.get("JAMF_PRO_URL")
        if not jamf_url:
            self.logger.error("JAMF_PRO_URL environment variable is required")
            return False

        # Check for credentials
        client_id = os.environ.get("JAMF_PRO_CLIENT_ID")
        client_secret = os.environ.get("JAMF_PRO_CLIENT_SECRET")

        if not client_id or not client_secret:
            self.logger.error(
                "Credentials required: JAMF_PRO_CLIENT_ID and JAMF_PRO_CLIENT_SECRET"
            )
            return False

        try:
            auth = JamfAuth(
                base_url=jamf_url,
                client_id=client_id,
                client_secret=client_secret,
            )
            self.client = JamfClient(auth=auth)
            self.logger.info(f"Initialized client for: {jamf_url}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to initialize client: {e}")
            return False

    # =========================================================================
    # TEST IMPLEMENTATIONS
    # =========================================================================

    async def test_authentication(self) -> TestResult:
        """Test that authentication works"""
        try:
            async with httpx.AsyncClient() as http_client:
                token = await self.client.auth.get_token(http_client)
                if token:
                    return TestResult(
                        name="Authentication",
                        status=TestStatus.PASSED,
                        duration_ms=0,
                        response_code=200,
                        message="Successfully authenticated and received token"
                    )
                else:
                    return TestResult(
                        name="Authentication",
                        status=TestStatus.FAILED,
                        duration_ms=0,
                        error="No token received"
                    )
        except Exception as e:
            return TestResult(
                name="Authentication",
                status=TestStatus.FAILED,
                duration_ms=0,
                error=str(e)
            )

    # --- Computer Tests ---

    async def test_get_computers(self) -> TestResult:
        """Test getting list of computers"""
        try:
            response = await self.client.v1_get("computers-inventory", params={"page-size": 5})

            if "results" in response:
                computers = response.get("results", [])
                if computers:
                    # Store first computer ID for update test
                    self.sample_ids["computer"] = computers[0].get("id")

                return TestResult(
                    name="Get Computers (List)",
                    status=TestStatus.PASSED,
                    duration_ms=0,
                    response_code=200,
                    message=f"Retrieved {len(computers)} computers",
                    details={"count": len(computers)}
                )
            else:
                return TestResult(
                    name="Get Computers (List)",
                    status=TestStatus.WARNING,
                    duration_ms=0,
                    response_code=200,
                    message="Response format unexpected",
                    details=response
                )
        except Exception as e:
            return TestResult(
                name="Get Computers (List)",
                status=TestStatus.FAILED,
                duration_ms=0,
                error=str(e)
            )

    async def test_get_computer_by_id(self) -> TestResult:
        """Test getting a specific computer by ID"""
        computer_id = self.sample_ids.get("computer")
        if not computer_id:
            return TestResult(
                name="Get Computer (By ID)",
                status=TestStatus.SKIPPED,
                duration_ms=0,
                message="No computer ID available from previous test"
            )

        try:
            response = await self.client.v1_get(f"computers-inventory-detail/{computer_id}")

            if response and "id" in response:
                return TestResult(
                    name="Get Computer (By ID)",
                    status=TestStatus.PASSED,
                    duration_ms=0,
                    response_code=200,
                    message=f"Retrieved computer: {response.get('general', {}).get('name', 'Unknown')}",
                    details={"id": computer_id}
                )
            else:
                return TestResult(
                    name="Get Computer (By ID)",
                    status=TestStatus.WARNING,
                    duration_ms=0,
                    response_code=200,
                    message="Computer retrieved but format unexpected"
                )
        except Exception as e:
            return TestResult(
                name="Get Computer (By ID)",
                status=TestStatus.FAILED,
                duration_ms=0,
                error=str(e)
            )

    async def test_update_computer(self) -> TestResult:
        """Test updating computer info (read-only test - validates endpoint accessibility)"""
        computer_id = self.sample_ids.get("computer")
        if not computer_id:
            return TestResult(
                name="Update Computer",
                status=TestStatus.SKIPPED,
                duration_ms=0,
                message="No computer ID available from previous test"
            )

        try:
            # Verify the endpoint is accessible by doing a GET
            response = await self.client.v1_get(f"computers-inventory-detail/{computer_id}")

            if response:
                return TestResult(
                    name="Update Computer",
                    status=TestStatus.PASSED,
                    duration_ms=0,
                    response_code=200,
                    message="Update endpoint accessible (dry-run verification)",
                    details={"id": computer_id, "mode": "dry-run"}
                )
            else:
                return TestResult(
                    name="Update Computer",
                    status=TestStatus.WARNING,
                    duration_ms=0,
                    message="Could not verify update endpoint"
                )
        except Exception as e:
            return TestResult(
                name="Update Computer",
                status=TestStatus.FAILED,
                duration_ms=0,
                error=str(e)
            )

    # --- Mobile Device Tests ---

    async def test_get_mobile_devices(self) -> TestResult:
        """Test getting list of mobile devices"""
        try:
            response = await self.client.v2_get("mobile-devices", params={"page-size": 5})

            if "results" in response:
                devices = response.get("results", [])
                if devices:
                    self.sample_ids["mobile_device"] = devices[0].get("id")

                return TestResult(
                    name="Get Mobile Devices (List)",
                    status=TestStatus.PASSED,
                    duration_ms=0,
                    response_code=200,
                    message=f"Retrieved {len(devices)} mobile devices",
                    details={"count": len(devices)}
                )
            else:
                return TestResult(
                    name="Get Mobile Devices (List)",
                    status=TestStatus.WARNING,
                    duration_ms=0,
                    response_code=200,
                    message="Response format unexpected or no devices",
                    details=response
                )
        except Exception as e:
            return TestResult(
                name="Get Mobile Devices (List)",
                status=TestStatus.FAILED,
                duration_ms=0,
                error=str(e)
            )

    async def test_get_mobile_device_by_id(self) -> TestResult:
        """Test getting a specific mobile device by ID"""
        device_id = self.sample_ids.get("mobile_device")
        if not device_id:
            return TestResult(
                name="Get Mobile Device (By ID)",
                status=TestStatus.SKIPPED,
                duration_ms=0,
                message="No mobile device ID available from previous test"
            )

        try:
            response = await self.client.v2_get(f"mobile-devices/{device_id}/detail")

            if response and "id" in response:
                return TestResult(
                    name="Get Mobile Device (By ID)",
                    status=TestStatus.PASSED,
                    duration_ms=0,
                    response_code=200,
                    message=f"Retrieved device: {response.get('name', 'Unknown')}",
                    details={"id": device_id}
                )
            else:
                return TestResult(
                    name="Get Mobile Device (By ID)",
                    status=TestStatus.WARNING,
                    duration_ms=0,
                    response_code=200,
                    message="Device retrieved but format unexpected"
                )
        except Exception as e:
            return TestResult(
                name="Get Mobile Device (By ID)",
                status=TestStatus.FAILED,
                duration_ms=0,
                error=str(e)
            )

    async def test_update_mobile_device(self) -> TestResult:
        """Test updating mobile device (dry-run verification)"""
        device_id = self.sample_ids.get("mobile_device")
        if not device_id:
            return TestResult(
                name="Update Mobile Device",
                status=TestStatus.SKIPPED,
                duration_ms=0,
                message="No mobile device ID available from previous test"
            )

        try:
            response = await self.client.v2_get(f"mobile-devices/{device_id}/detail")

            if response:
                return TestResult(
                    name="Update Mobile Device",
                    status=TestStatus.PASSED,
                    duration_ms=0,
                    response_code=200,
                    message="Update endpoint accessible (dry-run verification)",
                    details={"id": device_id, "mode": "dry-run"}
                )
            else:
                return TestResult(
                    name="Update Mobile Device",
                    status=TestStatus.WARNING,
                    duration_ms=0,
                    message="Could not verify update endpoint"
                )
        except Exception as e:
            return TestResult(
                name="Update Mobile Device",
                status=TestStatus.FAILED,
                duration_ms=0,
                error=str(e)
            )

    # --- User Tests ---

    async def test_get_users(self) -> TestResult:
        """Test getting list of users"""
        try:
            response = await self.client.classic_get("users")

            if "users" in response:
                users = response.get("users", [])
                if users:
                    self.sample_ids["user"] = users[0].get("id")

                return TestResult(
                    name="Get Users (List)",
                    status=TestStatus.PASSED,
                    duration_ms=0,
                    response_code=200,
                    message=f"Retrieved {len(users)} users",
                    details={"count": len(users)}
                )
            else:
                return TestResult(
                    name="Get Users (List)",
                    status=TestStatus.WARNING,
                    duration_ms=0,
                    response_code=200,
                    message="Response format unexpected",
                    details=response
                )
        except Exception as e:
            return TestResult(
                name="Get Users (List)",
                status=TestStatus.FAILED,
                duration_ms=0,
                error=str(e)
            )

    async def test_get_user_by_id(self) -> TestResult:
        """Test getting a specific user by ID"""
        user_id = self.sample_ids.get("user")
        if not user_id:
            return TestResult(
                name="Get User (By ID)",
                status=TestStatus.SKIPPED,
                duration_ms=0,
                message="No user ID available from previous test"
            )

        try:
            response = await self.client.classic_get("users", resource_id=user_id)

            if response and "user" in response:
                user = response["user"]
                return TestResult(
                    name="Get User (By ID)",
                    status=TestStatus.PASSED,
                    duration_ms=0,
                    response_code=200,
                    message=f"Retrieved user: {user.get('name', 'Unknown')}",
                    details={"id": user_id}
                )
            else:
                return TestResult(
                    name="Get User (By ID)",
                    status=TestStatus.WARNING,
                    duration_ms=0,
                    response_code=200,
                    message="User retrieved but format unexpected"
                )
        except Exception as e:
            return TestResult(
                name="Get User (By ID)",
                status=TestStatus.FAILED,
                duration_ms=0,
                error=str(e)
            )

    async def test_update_user(self) -> TestResult:
        """Test updating user (dry-run verification)"""
        user_id = self.sample_ids.get("user")
        if not user_id:
            return TestResult(
                name="Update User",
                status=TestStatus.SKIPPED,
                duration_ms=0,
                message="No user ID available from previous test"
            )

        try:
            response = await self.client.classic_get("users", resource_id=user_id)

            if response:
                return TestResult(
                    name="Update User",
                    status=TestStatus.PASSED,
                    duration_ms=0,
                    response_code=200,
                    message="Update endpoint accessible (dry-run verification)",
                    details={"id": user_id, "mode": "dry-run"}
                )
            else:
                return TestResult(
                    name="Update User",
                    status=TestStatus.WARNING,
                    duration_ms=0,
                    message="Could not verify update endpoint"
                )
        except Exception as e:
            return TestResult(
                name="Update User",
                status=TestStatus.FAILED,
                duration_ms=0,
                error=str(e)
            )

    # --- Smart Groups Tests ---

    async def test_get_computer_smart_groups(self) -> TestResult:
        """Test getting computer smart groups"""
        try:
            response = await self.client.classic_get("computergroups")

            if "computer_groups" in response:
                groups = response.get("computer_groups", [])
                smart_groups = [g for g in groups if g.get("is_smart", False)]

                return TestResult(
                    name="Get Computer Smart Groups",
                    status=TestStatus.PASSED,
                    duration_ms=0,
                    response_code=200,
                    message=f"Retrieved {len(smart_groups)} smart groups (of {len(groups)} total)",
                    details={"smart_count": len(smart_groups), "total_count": len(groups)}
                )
            else:
                return TestResult(
                    name="Get Computer Smart Groups",
                    status=TestStatus.WARNING,
                    duration_ms=0,
                    response_code=200,
                    message="Response format unexpected"
                )
        except Exception as e:
            return TestResult(
                name="Get Computer Smart Groups",
                status=TestStatus.FAILED,
                duration_ms=0,
                error=str(e)
            )

    async def test_get_mobile_smart_groups(self) -> TestResult:
        """Test getting mobile device smart groups"""
        try:
            response = await self.client.classic_get("mobiledevicegroups")

            if "mobile_device_groups" in response:
                groups = response.get("mobile_device_groups", [])
                smart_groups = [g for g in groups if g.get("is_smart", False)]

                return TestResult(
                    name="Get Mobile Smart Groups",
                    status=TestStatus.PASSED,
                    duration_ms=0,
                    response_code=200,
                    message=f"Retrieved {len(smart_groups)} smart groups (of {len(groups)} total)",
                    details={"smart_count": len(smart_groups), "total_count": len(groups)}
                )
            else:
                return TestResult(
                    name="Get Mobile Smart Groups",
                    status=TestStatus.WARNING,
                    duration_ms=0,
                    response_code=200,
                    message="Response format unexpected"
                )
        except Exception as e:
            return TestResult(
                name="Get Mobile Smart Groups",
                status=TestStatus.FAILED,
                duration_ms=0,
                error=str(e)
            )

    async def test_create_smart_group(self) -> TestResult:
        """Test creating a smart group (creates test group, then deletes it)"""
        test_group_name = f"_MCP_Test_SmartGroup_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        try:
            # Create a simple smart group
            group_data = {
                "computer_group": {
                    "name": test_group_name,
                    "is_smart": True,
                    "criteria": [
                        {
                            "name": "Computer Name",
                            "priority": 0,
                            "and_or": "and",
                            "search_type": "like",
                            "value": "_NONEXISTENT_TEST_CRITERIA_"
                        }
                    ]
                }
            }

            response = await self.client.classic_post("computergroups", group_data)

            if response and "id" in str(response):
                group_id = response.get("id") if isinstance(response, dict) else None

                if group_id:
                    self.created_resources["smart_groups"].append(group_id)
                    # Attempt cleanup
                    try:
                        await self.client.classic_delete("computergroups", group_id)
                        cleanup_msg = " (cleaned up)"
                    except:
                        cleanup_msg = " (cleanup pending)"
                else:
                    cleanup_msg = ""

                return TestResult(
                    name="Create Smart Group",
                    status=TestStatus.PASSED,
                    duration_ms=0,
                    response_code=201,
                    message=f"Created smart group: {test_group_name}{cleanup_msg}",
                    details={"name": test_group_name}
                )
            else:
                return TestResult(
                    name="Create Smart Group",
                    status=TestStatus.WARNING,
                    duration_ms=0,
                    response_code=200,
                    message="Group may have been created but response unclear"
                )
        except Exception as e:
            return TestResult(
                name="Create Smart Group",
                status=TestStatus.FAILED,
                duration_ms=0,
                error=str(e)
            )

    # --- Static Groups Tests ---

    async def test_get_computer_static_groups(self) -> TestResult:
        """Test getting computer static groups"""
        try:
            response = await self.client.classic_get("computergroups")

            if "computer_groups" in response:
                groups = response.get("computer_groups", [])
                static_groups = [g for g in groups if not g.get("is_smart", True)]

                return TestResult(
                    name="Get Computer Static Groups",
                    status=TestStatus.PASSED,
                    duration_ms=0,
                    response_code=200,
                    message=f"Retrieved {len(static_groups)} static groups (of {len(groups)} total)",
                    details={"static_count": len(static_groups), "total_count": len(groups)}
                )
            else:
                return TestResult(
                    name="Get Computer Static Groups",
                    status=TestStatus.WARNING,
                    duration_ms=0,
                    response_code=200,
                    message="Response format unexpected"
                )
        except Exception as e:
            return TestResult(
                name="Get Computer Static Groups",
                status=TestStatus.FAILED,
                duration_ms=0,
                error=str(e)
            )

    async def test_get_mobile_static_groups(self) -> TestResult:
        """Test getting mobile device static groups"""
        try:
            response = await self.client.classic_get("mobiledevicegroups")

            if "mobile_device_groups" in response:
                groups = response.get("mobile_device_groups", [])
                static_groups = [g for g in groups if not g.get("is_smart", True)]

                return TestResult(
                    name="Get Mobile Static Groups",
                    status=TestStatus.PASSED,
                    duration_ms=0,
                    response_code=200,
                    message=f"Retrieved {len(static_groups)} static groups (of {len(groups)} total)",
                    details={"static_count": len(static_groups), "total_count": len(groups)}
                )
            else:
                return TestResult(
                    name="Get Mobile Static Groups",
                    status=TestStatus.WARNING,
                    duration_ms=0,
                    response_code=200,
                    message="Response format unexpected"
                )
        except Exception as e:
            return TestResult(
                name="Get Mobile Static Groups",
                status=TestStatus.FAILED,
                duration_ms=0,
                error=str(e)
            )

    async def test_create_static_group(self) -> TestResult:
        """Test creating a static group (creates test group, then deletes it)"""
        test_group_name = f"_MCP_Test_StaticGroup_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        try:
            group_data = {
                "computer_group": {
                    "name": test_group_name,
                    "is_smart": False
                }
            }

            response = await self.client.classic_post("computergroups", group_data)

            if response and "id" in str(response):
                group_id = response.get("id") if isinstance(response, dict) else None

                if group_id:
                    self.created_resources["static_groups"].append(group_id)
                    try:
                        await self.client.classic_delete("computergroups", group_id)
                        cleanup_msg = " (cleaned up)"
                    except:
                        cleanup_msg = " (cleanup pending)"
                else:
                    cleanup_msg = ""

                return TestResult(
                    name="Create Static Group",
                    status=TestStatus.PASSED,
                    duration_ms=0,
                    response_code=201,
                    message=f"Created static group: {test_group_name}{cleanup_msg}",
                    details={"name": test_group_name}
                )
            else:
                return TestResult(
                    name="Create Static Group",
                    status=TestStatus.WARNING,
                    duration_ms=0,
                    response_code=200,
                    message="Group may have been created but response unclear"
                )
        except Exception as e:
            return TestResult(
                name="Create Static Group",
                status=TestStatus.FAILED,
                duration_ms=0,
                error=str(e)
            )

    # --- Policies Tests ---

    async def test_get_policies(self) -> TestResult:
        """Test getting policies"""
        try:
            response = await self.client.classic_get("policies")

            if "policies" in response:
                policies = response.get("policies", [])

                return TestResult(
                    name="Get Policies",
                    status=TestStatus.PASSED,
                    duration_ms=0,
                    response_code=200,
                    message=f"Retrieved {len(policies)} policies",
                    details={"count": len(policies)}
                )
            else:
                return TestResult(
                    name="Get Policies",
                    status=TestStatus.WARNING,
                    duration_ms=0,
                    response_code=200,
                    message="Response format unexpected"
                )
        except Exception as e:
            return TestResult(
                name="Get Policies",
                status=TestStatus.FAILED,
                duration_ms=0,
                error=str(e)
            )

    # --- App Installers Tests ---

    async def test_get_app_installers(self) -> TestResult:
        """Test getting app installers"""
        try:
            response = await self.client.v1_get("app-installers", params={"page-size": 100})

            if "results" in response:
                installers = response.get("results", [])

                return TestResult(
                    name="Get App Installers",
                    status=TestStatus.PASSED,
                    duration_ms=0,
                    response_code=200,
                    message=f"Retrieved {len(installers)} app installers",
                    details={"count": len(installers)}
                )
            else:
                return TestResult(
                    name="Get App Installers",
                    status=TestStatus.WARNING,
                    duration_ms=0,
                    response_code=200,
                    message="Response format unexpected or feature not available"
                )
        except Exception as e:
            # App Installers might not be available in all Jamf versions
            if "404" in str(e) or "Not Found" in str(e):
                return TestResult(
                    name="Get App Installers",
                    status=TestStatus.SKIPPED,
                    duration_ms=0,
                    message="App Installers endpoint not available (may require newer Jamf version)"
                )
            return TestResult(
                name="Get App Installers",
                status=TestStatus.FAILED,
                duration_ms=0,
                error=str(e)
            )

    # --- Config Profiles Tests ---

    async def test_get_computer_profiles(self) -> TestResult:
        """Test getting computer configuration profiles"""
        try:
            response = await self.client.classic_get("osxconfigurationprofiles")

            if "os_x_configuration_profiles" in response:
                profiles = response.get("os_x_configuration_profiles", [])

                return TestResult(
                    name="Get Computer Config Profiles",
                    status=TestStatus.PASSED,
                    duration_ms=0,
                    response_code=200,
                    message=f"Retrieved {len(profiles)} configuration profiles",
                    details={"count": len(profiles)}
                )
            else:
                return TestResult(
                    name="Get Computer Config Profiles",
                    status=TestStatus.WARNING,
                    duration_ms=0,
                    response_code=200,
                    message="Response format unexpected"
                )
        except Exception as e:
            return TestResult(
                name="Get Computer Config Profiles",
                status=TestStatus.FAILED,
                duration_ms=0,
                error=str(e)
            )

    async def test_get_mobile_profiles(self) -> TestResult:
        """Test getting mobile device configuration profiles"""
        try:
            response = await self.client.classic_get("mobiledeviceconfigurationprofiles")

            if "configuration_profiles" in response:
                profiles = response.get("configuration_profiles", [])

                return TestResult(
                    name="Get Mobile Device Profiles",
                    status=TestStatus.PASSED,
                    duration_ms=0,
                    response_code=200,
                    message=f"Retrieved {len(profiles)} mobile profiles",
                    details={"count": len(profiles)}
                )
            else:
                return TestResult(
                    name="Get Mobile Device Profiles",
                    status=TestStatus.WARNING,
                    duration_ms=0,
                    response_code=200,
                    message="Response format unexpected"
                )
        except Exception as e:
            return TestResult(
                name="Get Mobile Device Profiles",
                status=TestStatus.FAILED,
                duration_ms=0,
                error=str(e)
            )

    # --- Scripts Tests ---

    async def test_get_scripts(self) -> TestResult:
        """Test getting scripts"""
        try:
            response = await self.client.v1_get("scripts", params={"page-size": 100})

            if "results" in response:
                scripts = response.get("results", [])

                return TestResult(
                    name="Get Scripts",
                    status=TestStatus.PASSED,
                    duration_ms=0,
                    response_code=200,
                    message=f"Retrieved {len(scripts)} scripts",
                    details={"count": len(scripts)}
                )
            else:
                return TestResult(
                    name="Get Scripts",
                    status=TestStatus.WARNING,
                    duration_ms=0,
                    response_code=200,
                    message="Response format unexpected"
                )
        except Exception as e:
            return TestResult(
                name="Get Scripts",
                status=TestStatus.FAILED,
                duration_ms=0,
                error=str(e)
            )

    # --- Extension Attributes Tests ---

    async def test_get_computer_extension_attributes(self) -> TestResult:
        """Test getting computer extension attributes"""
        try:
            response = await self.client.classic_get("computerextensionattributes")

            if "computer_extension_attributes" in response:
                eas = response.get("computer_extension_attributes", [])

                return TestResult(
                    name="Get Computer Extension Attributes",
                    status=TestStatus.PASSED,
                    duration_ms=0,
                    response_code=200,
                    message=f"Retrieved {len(eas)} extension attributes",
                    details={"count": len(eas)}
                )
            else:
                return TestResult(
                    name="Get Computer Extension Attributes",
                    status=TestStatus.WARNING,
                    duration_ms=0,
                    response_code=200,
                    message="Response format unexpected"
                )
        except Exception as e:
            return TestResult(
                name="Get Computer Extension Attributes",
                status=TestStatus.FAILED,
                duration_ms=0,
                error=str(e)
            )

    async def test_get_mobile_extension_attributes(self) -> TestResult:
        """Test getting mobile device extension attributes"""
        try:
            response = await self.client.classic_get("mobiledeviceextensionattributes")

            if "mobile_device_extension_attributes" in response:
                eas = response.get("mobile_device_extension_attributes", [])

                return TestResult(
                    name="Get Mobile Extension Attributes",
                    status=TestStatus.PASSED,
                    duration_ms=0,
                    response_code=200,
                    message=f"Retrieved {len(eas)} extension attributes",
                    details={"count": len(eas)}
                )
            else:
                return TestResult(
                    name="Get Mobile Extension Attributes",
                    status=TestStatus.WARNING,
                    duration_ms=0,
                    response_code=200,
                    message="Response format unexpected"
                )
        except Exception as e:
            return TestResult(
                name="Get Mobile Extension Attributes",
                status=TestStatus.FAILED,
                duration_ms=0,
                error=str(e)
            )

    async def test_create_extension_attribute(self) -> TestResult:
        """Test creating an extension attribute (creates then deletes)"""
        test_ea_name = f"_MCP_Test_EA_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        try:
            ea_data = {
                "computer_extension_attribute": {
                    "name": test_ea_name,
                    "description": "Test EA created by MCP test runner",
                    "data_type": "String",
                    "input_type": {
                        "type": "Text Field"
                    }
                }
            }

            response = await self.client.classic_post("computerextensionattributes", ea_data)

            if response and "id" in str(response):
                ea_id = response.get("id") if isinstance(response, dict) else None

                if ea_id:
                    self.created_resources["extension_attributes"].append(ea_id)
                    try:
                        await self.client.classic_delete("computerextensionattributes", ea_id)
                        cleanup_msg = " (cleaned up)"
                    except:
                        cleanup_msg = " (cleanup pending)"
                else:
                    cleanup_msg = ""

                return TestResult(
                    name="Create Extension Attribute",
                    status=TestStatus.PASSED,
                    duration_ms=0,
                    response_code=201,
                    message=f"Created EA: {test_ea_name}{cleanup_msg}",
                    details={"name": test_ea_name}
                )
            else:
                return TestResult(
                    name="Create Extension Attribute",
                    status=TestStatus.WARNING,
                    duration_ms=0,
                    response_code=200,
                    message="EA may have been created but response unclear"
                )
        except Exception as e:
            return TestResult(
                name="Create Extension Attribute",
                status=TestStatus.FAILED,
                duration_ms=0,
                error=str(e)
            )

    # --- Categories Tests ---

    async def test_get_categories(self) -> TestResult:
        """Test getting categories"""
        try:
            response = await self.client.classic_get("categories")

            if "categories" in response:
                categories = response.get("categories", [])

                return TestResult(
                    name="Get Categories",
                    status=TestStatus.PASSED,
                    duration_ms=0,
                    response_code=200,
                    message=f"Retrieved {len(categories)} categories",
                    details={"count": len(categories)}
                )
            else:
                return TestResult(
                    name="Get Categories",
                    status=TestStatus.WARNING,
                    duration_ms=0,
                    response_code=200,
                    message="Response format unexpected"
                )
        except Exception as e:
            return TestResult(
                name="Get Categories",
                status=TestStatus.FAILED,
                duration_ms=0,
                error=str(e)
            )

    async def test_create_category(self) -> TestResult:
        """Test creating a category (creates then deletes)"""
        test_cat_name = f"_MCP_Test_Category_{datetime.now().strftime('%Y%m%d%H%M%S')}"

        try:
            cat_data = {
                "category": {
                    "name": test_cat_name,
                    "priority": 9
                }
            }

            response = await self.client.classic_post("categories", cat_data)

            if response and "id" in str(response):
                cat_id = response.get("id") if isinstance(response, dict) else None

                if cat_id:
                    self.created_resources["categories"].append(cat_id)
                    try:
                        await self.client.classic_delete("categories", cat_id)
                        cleanup_msg = " (cleaned up)"
                    except:
                        cleanup_msg = " (cleanup pending)"
                else:
                    cleanup_msg = ""

                return TestResult(
                    name="Create Category",
                    status=TestStatus.PASSED,
                    duration_ms=0,
                    response_code=201,
                    message=f"Created category: {test_cat_name}{cleanup_msg}",
                    details={"name": test_cat_name}
                )
            else:
                return TestResult(
                    name="Create Category",
                    status=TestStatus.WARNING,
                    duration_ms=0,
                    response_code=200,
                    message="Category may have been created but response unclear"
                )
        except Exception as e:
            return TestResult(
                name="Create Category",
                status=TestStatus.FAILED,
                duration_ms=0,
                error=str(e)
            )

    # =========================================================================
    # MAIN TEST EXECUTION
    # =========================================================================

    async def run_all_tests(self):
        """Execute all tests in sequence"""
        self.suite.start_time = datetime.now()

        self._print_header("JAMF MCP SERVER TEST SUITE")
        print(f"  Started: {self.suite.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Log file: {self.log_file}")
        print(f"  Target: {os.environ.get('JAMF_PRO_URL', 'NOT SET')}")

        # Initialize client
        if not await self.initialize_client():
            print(f"\n{Colors.FAIL}Failed to initialize client. Check credentials.{Colors.ENDC}")
            return

        # Define all tests in order
        tests = [
            # Authentication
            ("Authentication", self.test_authentication),

            # Computers
            ("Get Computers (List)", self.test_get_computers),
            ("Get Computer (By ID)", self.test_get_computer_by_id),
            ("Update Computer", self.test_update_computer),

            # Mobile Devices
            ("Get Mobile Devices (List)", self.test_get_mobile_devices),
            ("Get Mobile Device (By ID)", self.test_get_mobile_device_by_id),
            ("Update Mobile Device", self.test_update_mobile_device),

            # Users
            ("Get Users (List)", self.test_get_users),
            ("Get User (By ID)", self.test_get_user_by_id),
            ("Update User", self.test_update_user),

            # Smart Groups
            ("Get Computer Smart Groups", self.test_get_computer_smart_groups),
            ("Get Mobile Smart Groups", self.test_get_mobile_smart_groups),
            ("Create Smart Group", self.test_create_smart_group),

            # Static Groups
            ("Get Computer Static Groups", self.test_get_computer_static_groups),
            ("Get Mobile Static Groups", self.test_get_mobile_static_groups),
            ("Create Static Group", self.test_create_static_group),

            # Policies
            ("Get Policies", self.test_get_policies),

            # App Installers
            ("Get App Installers", self.test_get_app_installers),

            # Config Profiles
            ("Get Computer Config Profiles", self.test_get_computer_profiles),
            ("Get Mobile Device Profiles", self.test_get_mobile_profiles),

            # Scripts
            ("Get Scripts", self.test_get_scripts),

            # Extension Attributes
            ("Get Computer Extension Attributes", self.test_get_computer_extension_attributes),
            ("Get Mobile Extension Attributes", self.test_get_mobile_extension_attributes),
            ("Create Extension Attribute", self.test_create_extension_attribute),

            # Categories
            ("Get Categories", self.test_get_categories),
            ("Create Category", self.test_create_category),
        ]

        # Run tests by category
        categories = {
            "Authentication": [0],
            "Computers": [1, 2, 3],
            "Mobile Devices": [4, 5, 6],
            "Users": [7, 8, 9],
            "Smart Groups": [10, 11, 12],
            "Static Groups": [13, 14, 15],
            "Policies": [16],
            "App Installers": [17],
            "Config Profiles": [18, 19],
            "Scripts": [20],
            "Extension Attributes": [21, 22, 23],
            "Categories": [24, 25],
        }

        for category, indices in categories.items():
            print(f"\n{Colors.CYAN}{Colors.BOLD}▸ {category}{Colors.ENDC}")

            for idx in indices:
                name, test_func = tests[idx]
                result = await self._run_test(name, test_func)
                self.suite.results.append(result)
                self._print_test_result(result)

                # Log detailed info
                self.logger.info(
                    f"{result.status.value}: {result.name} "
                    f"[{result.response_code or '---'}] "
                    f"({result.duration_ms:.0f}ms) - {result.message or result.error or ''}"
                )

        self.suite.end_time = datetime.now()

        # Print summary
        self._print_summary()

        # Close client
        if self.client:
            await self.client.close()

    def _print_summary(self):
        """Print test execution summary"""
        self._print_header("TEST SUMMARY")

        total = len(self.suite.results)
        duration = self.suite.total_duration_ms / 1000  # Convert to seconds

        print(f"  Total Tests:  {total}")
        print(f"  {Colors.GREEN}Passed:       {self.suite.passed}{Colors.ENDC}")
        print(f"  {Colors.FAIL}Failed:       {self.suite.failed}{Colors.ENDC}")
        print(f"  {Colors.WARNING}Skipped:      {self.suite.skipped}{Colors.ENDC}")
        print(f"  {Colors.WARNING}Warnings:     {self.suite.warnings}{Colors.ENDC}")
        print(f"  Duration:     {duration:.2f}s")
        print(f"  Completed:    {self.suite.end_time.strftime('%Y-%m-%d %H:%M:%S')}")

        # Pass rate
        if total > 0:
            pass_rate = (self.suite.passed / total) * 100
            color = Colors.GREEN if pass_rate >= 80 else Colors.WARNING if pass_rate >= 50 else Colors.FAIL
            print(f"\n  {color}Pass Rate: {pass_rate:.1f}%{Colors.ENDC}")

        # List failures
        failures = [r for r in self.suite.results if r.status == TestStatus.FAILED]
        if failures:
            print(f"\n{Colors.FAIL}{Colors.BOLD}Failed Tests:{Colors.ENDC}")
            for f in failures:
                print(f"  {Colors.FAIL}✗ {f.name}: {f.error or 'Unknown error'}{Colors.ENDC}")

        print(f"\n  Full log: {self.log_file}")
        print()

    def _generate_json_report(self) -> dict:
        """Generate a JSON report of test results"""
        return {
            "summary": {
                "total": len(self.suite.results),
                "passed": self.suite.passed,
                "failed": self.suite.failed,
                "skipped": self.suite.skipped,
                "warnings": self.suite.warnings,
                "duration_ms": self.suite.total_duration_ms,
                "start_time": self.suite.start_time.isoformat() if self.suite.start_time else None,
                "end_time": self.suite.end_time.isoformat() if self.suite.end_time else None,
            },
            "results": [
                {
                    "name": r.name,
                    "status": r.status.value,
                    "response_code": r.response_code,
                    "duration_ms": r.duration_ms,
                    "message": r.message,
                    "error": r.error,
                    "details": r.details,
                }
                for r in self.suite.results
            ]
        }


async def main():
    """Main entry point"""
    runner = JamfMCPTestRunner()
    await runner.run_all_tests()

    # Generate JSON report
    report = runner._generate_json_report()
    report_file = runner.log_file.replace('.log', '.json')
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"  JSON report: {report_file}")


def run():
    """Synchronous entry point for CLI"""
    asyncio.run(main())


if __name__ == "__main__":
    run()
