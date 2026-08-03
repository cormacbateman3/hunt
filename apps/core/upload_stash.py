"""Retain uploaded files across a failed form submission.

A browser cannot repopulate `<input type="file">` after a POST, so a validation
error silently discarded whatever the user had uploaded and made them pick the
files again — on a form whose featured image is required, that is the most
annoying possible failure mode.

Files are stashed under MEDIA_ROOT and tracked in the **session**. The storage
path is deliberately never round-tripped through a form field: a client-supplied
path would let anyone name an arbitrary file and have the server attach it to
their own listing.
"""

import os
import uuid

from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile

SESSION_KEY = '_upload_stash'
STASH_DIR = 'tmp_uploads'

# Anything the create/edit forms accept. Guards against a stashed path being
# used to smuggle a non-image through a later request.
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}


def _bucket(request):
    return request.session.get(SESSION_KEY) or {}


def _save_bucket(request, bucket):
    if bucket:
        request.session[SESSION_KEY] = bucket
    else:
        request.session.pop(SESSION_KEY, None)
    request.session.modified = True


def stash_uploads(request, files):
    """Persist every uploaded file in `files` (a MultiValueDict) for one retry."""
    bucket = _bucket(request)
    for field in files:
        uploaded = files[field]
        ext = os.path.splitext(uploaded.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            continue
        # Replace any earlier stash for this field so the newest upload wins.
        _delete_path(bucket.pop(field, {}).get('path'))
        uploaded.seek(0)
        path = default_storage.save(f'{STASH_DIR}/{uuid.uuid4().hex}{ext}', uploaded)
        bucket[field] = {'path': path, 'name': uploaded.name}
    _save_bucket(request, bucket)


def restore_missing(request, files):
    """Return `files` with any stashed field the user did not re-upload.

    Returns the original object untouched when there is nothing to restore, so
    the common path allocates nothing.
    """
    bucket = _bucket(request)
    if not bucket:
        return files

    missing = [field for field in bucket if field not in files]
    if not missing:
        return files

    restored = files.copy()
    for field in missing:
        entry = bucket[field]
        if not default_storage.exists(entry['path']):
            continue
        handle = default_storage.open(entry['path'], 'rb')
        restored[field] = UploadedFile(
            file=handle,
            name=entry['name'],
            size=default_storage.size(entry['path']),
        )
    return restored


def stashed_files(request):
    """[(field, original filename, url)] for showing the user what was kept."""
    out = []
    for field, entry in _bucket(request).items():
        if default_storage.exists(entry['path']):
            out.append((field, entry['name'], default_storage.url(entry['path'])))
    return out


def _delete_path(path):
    if path and default_storage.exists(path):
        try:
            default_storage.delete(path)
        except OSError:
            # A stray temp file is harmless; the sweeper command will get it.
            pass


def clear_stash(request):
    """Drop every stashed file. Call once the form has actually saved."""
    for entry in _bucket(request).values():
        _delete_path(entry.get('path'))
    _save_bucket(request, {})
