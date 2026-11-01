"""Make the parser modules importable without Home Assistant."""

from __future__ import annotations

from pathlib import Path
import sys
import types

PACKAGE_DIR = Path(__file__).parents[2] / "custom_components" / "heating_prices"
FIXTURES = Path(__file__).parents[1] / "fixtures"

# Registering a bare package skips heating_prices/__init__.py, which imports
# Home Assistant. The modules under test only use relative imports.
if "heating_prices" not in sys.modules:
    package = types.ModuleType("heating_prices")
    package.__path__ = [str(PACKAGE_DIR)]
    sys.modules["heating_prices"] = package
