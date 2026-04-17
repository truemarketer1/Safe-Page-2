import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Keep secret-gated verifiers in "open" mode for unit tests (we'll explicitly
# set secrets in the tests that exercise signature paths).
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "")
os.environ.setdefault("META_APP_SECRET", "")
os.environ.setdefault("CAL_WEBHOOK_SECRET", "")
os.environ.setdefault("RETELL_WEBHOOK_SECRET", "")
os.environ.setdefault("MANYCHAT_WEBHOOK_SECRET", "")
