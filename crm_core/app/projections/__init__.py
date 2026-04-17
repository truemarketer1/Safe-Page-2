"""One projector per external source.

Each projector takes a raw `events` row and writes into the domain tables
(leads, conversations, messages, appointments, calls, payments). Projectors are
idempotent — replaying the same event row produces the same end state.
"""

from .cal import project_cal
from .manychat import project_manychat
from .meta import project_meta
from .retell import project_retell
from .stripe import project_stripe

__all__ = [
    "project_cal",
    "project_manychat",
    "project_meta",
    "project_retell",
    "project_stripe",
    "PROJECTORS",
]

PROJECTORS = {
    "cal": project_cal,
    "manychat": project_manychat,
    "meta": project_meta,
    "retell": project_retell,
    "stripe": project_stripe,
}
