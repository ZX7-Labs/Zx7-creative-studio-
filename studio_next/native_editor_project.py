"""Open an owner-selected native project before model-directed editing.

This is explicit host setup, not a model creative decision. Its separate
append-only receipt never counts as model-selected editing evidence.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile

from .body_editor_client import _load_json
from .native_editor_diagnostics import native_content_diagnostics_source_verified


def checkpoint_saved_project(project: Path, destination: Path):
    """Keep the exact saved native document outside the editor's writable roots."""
    saved = project / "project.comfystudio"
    if project.resolve(strict=True) != project:
        raise ValueError("Saved native project directory was redirected")
    if saved.is_symlink():
        raise ValueError("Saved native project file must not be a symbolic link")

    def identity(info):
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)

    digest = hashlib.sha256()
    size = 0
    with open(saved, "rb", opener=lambda p, f: os.open(p, f | os.O_NOFOLLOW | os.O_NONBLOCK)) as source:
        before = os.fstat(source.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size == 0:
            raise ValueError("Saved native project file must be a nonempty regular file")
        with tempfile.NamedTemporaryFile(dir=destination.parent, prefix=".prior-project-") as copy:
            while chunk := source.read(1024 * 1024):
                size += len(chunk)
                if size > before.st_size:
                    raise ValueError("Saved native project file changed while taking a checkpoint")
                copy.write(chunk)
                digest.update(chunk)
            copy.flush()
            os.fsync(copy.fileno())
            if (size != before.st_size or project.resolve(strict=True) != project or
                    identity(before) != identity(saved.stat(follow_symlinks=False))):
                raise ValueError("Saved native project file changed while taking a checkpoint")
            os.link(copy.name, destination)

    return {"path": str(destination), "project": str(project), "bytes": size,
            "sha256": digest.hexdigest()}


def _receipt(result):
    if hasattr(result, 'model_dump'):
        result = result.model_dump(by_alias=True)
    if not isinstance(result, dict) or result.get('isError', result.get('is_error', False)):
        raise RuntimeError('Native project setup returned an error; do not replay the open')
    blocks = result.get('content')
    if (not isinstance(blocks, list) or len(blocks) != 1 or
            not isinstance(blocks[0], dict) or blocks[0].get('type') != 'text' or
            not isinstance(blocks[0].get('text'), str) or len(blocks[0]['text']) > 1024 * 1024):
        raise RuntimeError('Native project setup returned an ambiguous receipt')
    value = _load_json(blocks[0]['text'])
    if not isinstance(value, dict):
        raise RuntimeError('Native project setup needs an object receipt')
    return value


async def open_selected_native_project(session, *, project, source, projects_root,
                                       grants, receipt_path):
    selected = Path(project).resolve(strict=True)
    if (not selected.is_dir() or not selected.is_relative_to(Path(projects_root).resolve(strict=True))
            or not (selected / 'project.comfystudio').is_file()):
        raise ValueError('Select a saved project within the authorized projects root')
    if grants.get('open_project') != 'write' or grants.get('get_project') != 'read':
        raise ValueError('Selected-project setup requires granted open_project and get_project')
    if not native_content_diagnostics_source_verified(Path(source)):
        raise ValueError('Selected-project setup requires independently attested native source')
    # Reserve a new receipt before dispatch. An interrupted attempt is retained
    # and can never cause this helper to replay into the same receipt.
    with open(receipt_path, 'x', encoding='utf-8',
              opener=lambda p, f: os.open(p, f, 0o600)) as out:
        def record(phase):
            out.write(json.dumps({'phase': phase, 'owner_selected_project_sha256':
                hashlib.sha256(str(selected).encode()).hexdigest(),
                'model_selected_action': False, 'automatic_write_replay': False}) + '\n')
            out.flush()
            os.fsync(out.fileno())
        record('open_submitted')
        opened = _receipt(await session.call_tool('open_project', {
            'projectPath': str(selected), 'previewOnly': False}))
        if opened.get('success') is not True or opened.get('action') != 'open_project':
            raise RuntimeError('Selected project open was not acknowledged; do not replay')
        record('open_acknowledged')
        # A native snapshot can trail the renderer's acknowledgement. Poll only
        # the read; never repeat the project switch or start edits on mismatch.
        for attempt in range(10):
            active = _receipt(await session.call_tool('get_project', {})).get('project')
            actual = active.get('path') if isinstance(active, dict) else None
            if isinstance(actual, str) and Path(actual).is_absolute() and Path(actual).resolve() == selected:
                record('active_project_verified')
                return {'owner_selected_project_opened': True,
                        'active_project_identity_verified': True,
                        'model_selected_action': False}
            if attempt < 9:
                await asyncio.sleep(0.2)
        raise RuntimeError('Active native project differs from owner selection; editing not started')
