# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Luk Verhelst
"""No test reaches the network: the SDK is pointed at a closed port with a fake key."""

import os

os.environ["ANTHROPIC_API_KEY"] = "test"
os.environ["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:9"
