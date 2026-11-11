# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2026 Lin Zihan and the hsolve contributors
"""pytest configuration: make the repository root importable (tools.* packages)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
