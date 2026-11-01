"""Shared test setup.

Parser tests in tests/providers run with plain pytest. Tests that need Home
Assistant live in tests/integration and only run when
pytest-homeassistant-custom-component is installed (as in CI).
"""

from __future__ import annotations

import importlib.util

HAS_HOME_ASSISTANT = (
    importlib.util.find_spec("pytest_homeassistant_custom_component") is not None
)

collect_ignore = [] if HAS_HOME_ASSISTANT else ["integration"]
