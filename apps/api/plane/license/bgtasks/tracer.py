# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Third party imports
from celery import shared_task


@shared_task
def instance_traces():
    """Disable remote telemetry trace collection for self-managed installations."""
    return
