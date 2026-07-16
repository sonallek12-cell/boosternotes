"""
myapp/signals.py

Auto-backup: whenever any model in this app is saved or deleted,
schedule a Dropbox backup after a 60-second debounce window.
This prevents backup storms when bulk-saving many records at once.
The backup always runs in a background thread so it never blocks
the HTTP response.
"""
import logging
import threading

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.apps import apps

logger = logging.getLogger(__name__)

# ── Debounce state ─────────────────────────────────────────────────────────
_backup_timer: threading.Timer | None = None
_backup_lock = threading.Lock()
DEBOUNCE_SECONDS = 60  # wait this long after the last change before backing up

# Models whose saves/deletes should NOT trigger a backup
# (Order / OrderItem change very frequently during payments)
_SKIP_MODELS = {'order', 'orderitem', 'couponusage'}


def _run_backup():
    """Execute the actual Dropbox backup (runs in a background thread)."""
    try:
        from myapp.db_backup import backup_to_dropbox
        timestamp = backup_to_dropbox()
        logger.info("[AutoBackup] Backup completed: db_%s.sqlite3", timestamp)
    except Exception as exc:
        logger.error("[AutoBackup] Backup failed: %s", exc)


def _schedule_backup():
    """Cancel any pending backup timer and start a fresh debounced one."""
    global _backup_timer
    with _backup_lock:
        if _backup_timer is not None:
            _backup_timer.cancel()
        _backup_timer = threading.Timer(DEBOUNCE_SECONDS, _run_backup)
        _backup_timer.daemon = True
        _backup_timer.start()


def _should_backup(sender):
    """Return True if a change to *sender* should trigger a backup."""
    model_name = sender.__name__.lower()
    return model_name not in _SKIP_MODELS


# ── Connect signals to ALL models in this app ──────────────────────────────

@receiver(post_save)
def on_model_saved(sender, **kwargs):
    try:
        app_label = sender._meta.app_label
    except Exception:
        return
    if app_label != 'myapp':
        return
    if not _should_backup(sender):
        return
    logger.debug("[AutoBackup] Change detected on %s — scheduling backup.", sender.__name__)
    _schedule_backup()


@receiver(post_delete)
def on_model_deleted(sender, **kwargs):
    try:
        app_label = sender._meta.app_label
    except Exception:
        return
    if app_label != 'myapp':
        return
    if not _should_backup(sender):
        return
    logger.debug("[AutoBackup] Deletion detected on %s — scheduling backup.", sender.__name__)
    _schedule_backup()
