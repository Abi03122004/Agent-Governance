"""Pytest configuration for agent-security test suite."""

import os

# Explicit development authentication configuration for test harnesses
os.environ["ALLOW_DEV_HEADER_AUTH"] = "true"
