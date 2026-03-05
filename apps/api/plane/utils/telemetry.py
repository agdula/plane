# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.


def init_tracer():
    """Disable OpenTelemetry initialization for self-managed installations."""
    return None


def shutdown_tracer():
    """No-op because telemetry exporters are disabled."""
    return None
