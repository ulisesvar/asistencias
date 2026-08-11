import sys
import time
from pathlib import Path

from . import config

MAX_AGE_SECONDS = config.HEARTBEAT_INTERVAL_SECONDS * 3


def main() -> int:
    heartbeat = Path(config.HEARTBEAT_FILE)
    if not heartbeat.exists():
        return 1
    age = time.time() - heartbeat.stat().st_mtime
    return 0 if age <= MAX_AGE_SECONDS else 1


if __name__ == "__main__":
    sys.exit(main())
