"""Feature flag: manual /who-am-i person picker (dev / experiments only)."""

import os

_ENV = "TWFAMILY_WHOAMI_EXPERIMENT"


def is_whoami_experiment_enabled() -> bool:
    v = (os.environ.get(_ENV) or "").strip().lower()
    return v in ("1", "true", "yes", "on")
