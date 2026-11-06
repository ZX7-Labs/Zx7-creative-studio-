"""Bounded real CPU-model/native-editor trial. Never supplies editing actions.

The generated media are neutral owned test inputs, not a prescribed edit. The
identified neural model chooses every editor mutation. This does not certify
professional creative quality, source rights beyond these fixtures or isolation.
"""
import argparse
import asyncio
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tarfile
import time
from urllib.parse import urlsplit
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from studio_next.native_creative_control import NativeCreativeControl, NATIVE_CREATIVE_SYSTEM
from studio_next.native_creative_audit import audit_native_journal, read_native_journal
from studio_next.providers import LocalCreativeModel, LocalModelSettings
from studio_next.native_action_schema import native_action_schema


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def parse_linux_proc_peak_rss(status_text):
    """Peak RSS of one live model-server PID; never extrapolate system RAM.

    Linux procfs VmHWM is a per-process high-water resident set in KiB.
    It does not include the Electron editor, OS page cache, or every shared
    mapping's machine-wide cost. Invalid/missing status is *unmeasured*.
    """
    if not isinstance(status_text, str):
        return None
    entries = [line.split(":", 1)[1].strip() for line in status_text.splitlines()
               if line.startswith("VmHWM:")]
    if len(entries) != 1:
        return None
    parts = entries[0].split()
    if len(parts) != 2 or parts[1] != "kB" or not parts[0].isdecimal():
        return None
    kib = int(parts[0])
    if not 0 < kib <= 1024 * 1024 * 1024:
        return None
    return kib * 1024


def read_live_linux_model_peak_rss(pid):
    """Observe the specific still-running server; absent procfs fails closed."""
    if os.name != "posix" or sys.platform != "linux" or type(pid) is not int or pid <= 0:
        return None
    try:
        return parse_linux_proc_peak_rss(
            Path(f"/proc/{pid}/status").read_text(encoding="ascii"))
    except (OSError, UnicodeError):
        return None


def download(entry, root):
    # A research manifest is committed code, not permission to write arbitrary
    # filesystem paths or fetch local URLs during a privileged CI trial.
    name = entry.get('filename')
    url = entry.get('url')
    digest = entry.get('sha256')
    if (not isinstance(name, str) or not name or
            Path(name).name != name or name in (".", "..") or
            chr(92) in name or chr(0) in name):
        raise ValueError('Model input filename must be a safe basename')
    parsed = urlsplit(url) if isinstance(url, str) else None
    if (parsed is None or parsed.scheme != 'https' or not parsed.hostname or
            parsed.username is not None or parsed.password is not None or
            parsed.fragment or parsed.hostname in ('localhost', '127.0.0.1', '::1')):
        raise ValueError('Pinned inputs require a credential-free remote HTTPS URL')
    if (not isinstance(digest, str) or len(digest) != 64 or
            any(c not in '0123456789abcdef' for c in digest)):
        raise ValueError('Pinned download requires an exact lower-case SHA256')
    target = root / name
    if target.is_symlink():
        raise ValueError('Pinned weight target cannot be a symbolic link')
    expected = entry.get('bytes')
    limit = expected if type(expected) is int else entry.get('max_bytes')
    if (type(limit) is not int or not 0 < limit <= 10_000_000_000 or
            (expected is not None and (type(expected) is not int or expected != limit))):
        raise ValueError('Pinned input requires verified byte size or strict download upper bound')
    if target.is_file() and target.stat().st_size <= limit and (
            expected is None or target.stat().st_size == expected) and sha(target) == entry['sha256']:
        return target
    partial = target.with_suffix(target.suffix + '.partial')
    print('Downloading pinned input:', entry['filename'], flush=True)
    try:
        # Exclusive create avoids following an attacker-controlled partial
        # symlink; no unsafe overwrite of a prior incomplete download.
        fd = os.open(partial, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as dest, urlopen(entry['url'], timeout=120) as response:
            count = 0
            while block := response.read(1024 * 1024):
                count += len(block)
                if count > limit:
                    raise ValueError('Download exceeds pinned safety bound')
                dest.write(block)
        if ((expected is not None and partial.stat().st_size != expected) or
                partial.stat().st_size <= 0 or sha(partial) != entry['sha256']):
            raise ValueError('Pinned download identity mismatch: ' + entry['filename'])
        partial.replace(target)
        return target
    finally:
        if partial.exists():
            partial.unlink()


class RecordedModel:
    """Trial-only passive transcript; all returned decisions come from inference."""
    def __init__(self, model, artifacts):
        self.model, self.settings, self.artifacts = model, model.settings, artifacts
        self.turn = 0

    @property
    def last_call_usage(self):
        return self.model.last_call_usage

    def infer(self, context, images=()):
        started = time.monotonic()
        self.model.settings.sampling['response_format'] = {'type': 'json_schema', 'json_schema': {
            'name': 'native_editor_action', 'strict': True,
            'schema': native_action_schema(context['actual_granted_native_tools'],
                 compact_catalog=context.get('compact_tool_catalog', False),
                 selected_tools=context.get('selectable_native_tools', []),
                 inspectable_tools=context.get('inspectable_native_tools', []),
                 allow_finish=not context.get('missing_completion_evidence', []))}}
        record = {'turn': self.turn, 'context': context, 'image_sha256': []}
        for index, (_, raw) in enumerate(images):
            path = self.artifacts / 'observations' / f'{self.turn}-{index}.png'
            path.parent.mkdir(exist_ok=True)
            path.write_bytes(raw)
            record['image_sha256'].append(sha(path))
        try:
            decision = (self.model.decide_with_images(context, images) if images
                        else self.model.decide(context))
            record['decision'] = decision
            return decision
        except BaseException as exc:
            record['error_type'] = type(exc).__name__
            raise
        finally:
            record['measured_wall_seconds'] = time.monotonic() - started
            record['server_reported_token_usage'] = self.model.last_call_usage
            with (self.artifacts / 'inference-transcript.jsonl').open('a') as journal:
                journal.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n')
            print('Actual model turn', self.turn, 'seconds', round(record['measured_wall_seconds'], 2),
                  'action', record.get('decision', {}).get('action', 'failed'), flush=True)
            self.turn += 1

    def decide(self, context):
        return self.infer(context)

    def decide_with_images(self, context, images):
        return self.infer(context, images)


def fresh_trial_project_open_effects(projects_root):
    """Host-attested possibilities for a NEW empty native-editor trial.

    An open_project call requires an existing native project, which this
    isolated test root cannot contain before the first creation. It remains
    host-granted for later legitimate choices; it must not be advertised as an
    *initial* way to establish project_open without actual existing source.
    This is a trial-scoped machine fact, NOT a creative operation plan.
    """
    root = Path(projects_root)
    if not root.is_dir() or any(root.iterdir()):
        raise ValueError("Native trial requires a new empty project directory")
    return {"create_project": ["project_open"]}


async def trial(args, lock, artifacts, command):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    projects, staging, outputs = (artifacts / name for name in ('projects', 'staging', 'outputs'))
    for root in (projects, staging, outputs):
        root.mkdir()
    initial_project_effects = fresh_trial_project_open_effects(projects)
    # Pinned Velorn src/services/mcpActions.js
    # handleImportAssetFromPath applies useAssetsStore.addAsset only after a
    # real previewOnly:false import. This HOST fact says that import *may*
    # create a project asset; it does not choose imports, clips or edits.
    # Actual asset presence remains gated by live get_assets reads.
    initial_project_effects["import_asset_from_path"] = [
        "project_asset_available"]
    # Raw, neutral media available to the model; no timeline or artwork authored.
    source_assets = []
    for index, colors in enumerate((('0x102030', '0x607080'), ('0x302010', '0x807060'))):
        path = staging / f'raw-gradient-{index}.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
            f'gradients=s=640x360:r=24:d=4:c0={colors[0]}:c1={colors[1]}:seed={index + 10}',
            '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(path)], check=True, timeout=60)
        source_assets.append({'path': str(path), 'sha256': sha(path),
                              'rights': 'original generated neutral trial input'})
    (artifacts / 'source-assets.json').write_text(json.dumps(source_assets, indent=2))
    config = json.loads((ROOT / 'engines/velorn/editor.example.json').read_text())
    for helper in ('get_ai_review_passes', 'get_mcp_recipes'):
        config['allowed_tools'].pop(helper, None)  # No canned creative recipes in this trial.
    config.update(projects_root=str(projects), staging_root=str(staging), outputs_root=str(outputs),
                  verify_native_exports=True)
    config_path = artifacts / 'host-grants.json'
    config_path.write_text(json.dumps(config, indent=2))
    brief = (
        'Create an original short editable motion piece about "Small steps, clear progress". '
        'Choose the composition, typography, pacing, visual treatment and message yourself. '
        'Use any of the provided original neutral footage as raw material; they are not a storyboard. '
        'Deliver an actual native project and MP4 in the dedicated output folder. '
        'Inspect a physically verified frame of your export, independently identify an improvement, '
        'make that editable change and deliver a new verified export. Save your native work. '
        'This is a CPU technical trial: keep the film at most eight seconds and 640x360, '
        'with small bounded state queries. Those are trial resource bounds, not product/style limits. '
        'Your model supports text and images, not native WAV listening; do not claim hearing. '
        'Known exporter limitation: at least one imported image/video must appear on the visual timeline. '
        f'Projects folder: {projects}. Output folder: {outputs}. '
        'Available source assets: ' + json.dumps(source_assets))
    (artifacts / 'brief.txt').write_text(brief)
    params = [str(ROOT / 'engines/velorn/mcp.mjs'), '--source', str(args.source),
              '--config', str(config_path), '--state', str(args.runtime / 'editor-state'),
              '--python', sys.executable, '--xvfb-binary', args.xvfb_binary, '--display', args.display]
    model = RecordedModel(LocalCreativeModel(LocalModelSettings(
        model_id=lock['server']['alias'], base_url='http://127.0.0.1:8080', timeout_seconds=300),
        system_prompt=NATIVE_CREATIVE_SYSTEM), artifacts)
    # This mapping originates in the trusted host config, not the
    # replaceable neural model. Only READ errors may be safely corrected.
    host = dict(config['allowed_tools'])
    host.update({name: 'read' for name in ('zx7_verify_native_export',
        'zx7_observe_verified_export_frame', 'zx7_observe_verified_export_samples',
        'zx7_observe_verified_export_audio', 'zx7_observe_verified_export_audio_timeline')})
    content_tools = {'update_text_clip', 'update_shape_clip', 'set_clip_style', 'set_clip_mask',
        'set_clip_keyframes', 'set_clip_audio', 'set_clip_speed', 'move_clips', 'trim_clips',
        'delete_clips', 'add_asset_to_timeline', 'add_assets_to_timeline', 'replace_clip_with_asset',
        'add_text_clip', 'add_shape_clip', 'add_solid_color', 'add_adjustment_clip', 'duplicate_clip',
        'add_transition', 'update_transition', 'remove_transitions', 'add_glsl_effect',
        'update_glsl_effect', 'remove_glsl_effect', 'set_master_audio', 'update_track', 'remove_track'}
    # Trusted native role inventory, never derived from model utterances:
    # save/export create files but are not artistic content revisions.
    host_content_revision_tools = tuple(sorted(
        name for name in content_tools if host.get(name) == "write"))
    completion_evidence = (
        "native_write_acknowledged",
        "physical_export_verified",
        "post_observation_native_write_acknowledged",
        "verified_export_frame_observed",
    )
    with (artifacts / 'editor-stderr.log').open('w') as log:
        async with stdio_client(StdioServerParameters(command='node', args=params, cwd=ROOT), errlog=log) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=180) as session:
                await session.initialize()
                try:
                    outcome = await asyncio.wait_for(NativeCreativeControl(session, model, max_turns=48,
                    receipt_path=artifacts / 'native-journal.jsonl',
                    host_tool_access=host, catalog_mode="indexed",
                    host_preconditions={
                        "import_asset_from_path": ["project_open"],
                        "add_asset_to_timeline": ["project_open"],
                        "add_assets_to_timeline": ["project_open"],
                        # The second physical 2B trial attempted a native
                        # replacement after an acknowledged create but before
                        # the project was independently observable. A write
                        # with no native timeline must not be dispatched;
                        # fail preflight and let the model re-inspect reality.
                        "replace_clip_with_asset": ["project_open"],
                        "add_text_clip": ["project_open"],
                        "save_project": ["project_open"],
                        "export_timeline": ["project_open"],
                    },
                    host_possible_effects=initial_project_effects,
                    # The bounded trial authors one project. A second neural
                    # create request after an acknowledged write may destroy
                    # continuity or create an unrelated empty project. Other
                    # creative sessions are not globally subject to this rule.
                    host_once_after_acknowledged_write=("create_project",),
                    # Technical owner acceptance facts, NOT an editing plan.
                    # Failed model claims cannot end the trial before actual
                    # native activity, source-verified export and visual sensing.
                    required_evidence=completion_evidence,
                    host_content_revision_tools=host_content_revision_tools).run(brief),
                    timeout=2400)
                except Exception as trial_error:
                    # A disk-full/write failure while preserving a diagnostic
                    # must never mask the actual editor/model failure.
                    try:
                        preserve_native_trial_failure_audit(
                            artifacts, host_tool_access=host,
                            expected_required_evidence=completion_evidence,
                            host_content_revision_tools=host_content_revision_tools)
                    except Exception as audit_error:
                        trial_error.add_note(
                            "Partial native audit preservation failed: " +
                            type(audit_error).__name__)
                    # An incomplete or timed-out run is *still a failure*.
                    # Never let an audited prefix masquerade as a movie.
                    raise
    audit = audit_native_journal(
        read_native_journal(artifacts / 'native-journal.jsonl'),
        host_tool_access=host, expected_required_evidence=completion_evidence,
        host_content_revision_tools=host_content_revision_tools)
    (artifacts / 'journal-audit.json').write_text(json.dumps(audit, indent=2))
    actual_images = len(list((artifacts / 'observations').glob('*.png')))
    movies = {}
    for path in outputs.glob('*.mp4'):
        movies.setdefault(sha(path), set()).add(path.resolve())
    decisions = {record['context']['turn']: record['decision']
        for record in map(json.loads, (artifacts / 'inference-transcript.jsonl').read_text().splitlines())
        if 'decision' in record}
    observed_sources, revisions, last_revision, last_save, revised_exports = set(), 0, -1, -1, []
    exported_after_revision = set()
    # Only actual native export ACKs can bind a model-requested timeline
    # range to a physically verified resulting movie. Untrusted model text
    # alone is never a delivery/custody attestation.
    export_inputs_by_path = {}
    for index, event in enumerate(outcome['events']):
        if event.get('kind') != 'native_tool_result':
            continue
        if event.get('tool') == 'save_project':
            last_save = index
        if observed_sources and event.get('tool') in content_tools:
            revisions += 1
            last_revision = index
            revised_exports = []
            exported_after_revision = set()
            export_inputs_by_path = {}
        if last_revision >= 0 and event.get('tool') == 'export_timeline':
            selected = decisions[event['turn']]['arguments']['inputs']
            output_path = selected.get('outputPath')
            if isinstance(output_path, str) and output_path:
                resolved = Path(output_path).resolve()
                # Exact trial output root, not a model-authored arbitrary path.
                if resolved.is_relative_to(outputs.resolve()):
                    exported_after_revision.add(resolved)
                    export_inputs_by_path[resolved] = selected
        verified = event.get('independently_verified_export_sha256')
        if (last_revision >= 0 and verified and verified not in observed_sources
                and movies.get(verified, set()) & exported_after_revision):
            revised_exports.append(verified)
        if event.get('image_sha256') and event.get('observed_export_sha256'):
            observed_sources.add(event['observed_export_sha256'])
    native_projects = [path for path in projects.glob('*/project.comfystudio')
        if any(timeline.get('clips') for timeline in json.loads(path.read_text()).get('timelines', []))]
    # A project, animated synthetic background, or typography alone is not
    # proof that the creative model edited the ORIGINAL caller-supplied videos.
    # The pinned editor stores sourcePath and project-owned copied media after
    # a real import_asset_from_path. Verify those physical bytes, then require
    # a saved timeline clip to reference the actual imported asset identity.
    # No source is imported on the model's behalf, no edit is scripted.
    from studio_next.native_source_acceptance import (
        verify_original_footage_on_native_timeline)
    # Pinned Velorn resolves full export to max(saved duration, clip ends),
    # and custom exports from model-authored startSeconds/endSeconds. Saved
    # timeline.duration therefore CANNOT by itself prove what part of the
    # source entered the actual MP4. Bind intervals to physically checked
    # SHA-256, a real acknowledged export path, and its decoded VIDEO stream
    # duration. Nothing is inferred from an unverified model claim.
    host_verified_export_windows = []
    for movie_digest in sorted(set(revised_exports)):
        for movie in sorted(movies.get(movie_digest, set()) & exported_after_revision):
            inputs = export_inputs_by_path.get(movie)
            if not isinstance(inputs, dict) or sha(movie) != movie_digest:
                continue
            start = inputs.get('startSeconds', 0)
            # Do not silently coerce an invalid model string, NaN or bool
            # into a plausible time origin; the editor remains the judge of
            # all valid native actions.
            if type(start) not in (int, float) or not math.isfinite(start) or start < 0:
                continue
            raw_duration = subprocess.check_output([
                'ffprobe', '-v', 'error', '-select_streams', 'v:0',
                '-show_entries', 'stream=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(movie)], timeout=30).decode('utf-8').strip()
            try:
                duration = float(raw_duration)
            except ValueError:
                continue
            if not math.isfinite(duration) or duration <= 0:
                continue
            if not math.isfinite(start + duration):
                continue
            host_verified_export_windows.append({
                'start_seconds': start, 'end_seconds': start + duration})
    original_footage = verify_original_footage_on_native_timeline(
        projects, native_projects, source_assets,
        host_verified_export_windows=host_verified_export_windows)
    def decoded_frames(path):
        raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path),
            '-map', '0:v:0', '-f', 'framemd5', '-'], timeout=60).decode()
        return [line.split(',')[-1].strip() for line in raw.splitlines() if line and not line.startswith('#')]
    changed_pixels = any(decoded_frames(next(iter(movies[before]))) != decoded_frames(next(iter(movies[after])))
        for before in observed_sources for after in revised_exports if before in movies and after in movies)
    passed = (outcome['status'] == 'model_finished_unverified' and actual_images > 0
              and revisions > 0 and last_save > last_revision and bool(native_projects)
              and original_footage['actual_original_video_used_on_native_timeline']
              and bool(revised_exports) and changed_pixels)
    return {'technical_trial_completed': passed, 'model_status': outcome['status'],
            'image_inputs_actually_sent': actual_images, 'content_mutations_after_observation': revisions,
            'decoded_frame_sequence_changed': changed_pixels,
            'verified_exports_after_final_revision': revised_exports,
            'saved_native_projects': [str(path.relative_to(artifacts)) for path in native_projects],
            'original_source_footage_on_native_timeline_verified':
                original_footage['actual_original_video_used_on_native_timeline'],
            'native_original_source_clip_proof':
                original_footage['verified_native_source_clip_proof'],
            'host_bound_verified_export_time_windows':
                host_verified_export_windows,
            'audit': audit,
            'acceptance_note': 'Source-chain and model-operation evidence only, not artistic acceptance'}



def preserve_native_trial_failure_audit(
        artifacts, *, host_tool_access, expected_required_evidence,
        host_content_revision_tools):
    """Preserve independently checked *partial* journal on trial failure.

    A 40-minute CPU model budget may cancel an inference after valid previous
    editor calls. Failure must retain an independently verifiable journal and
    explicit NOT-complete metadata, never manufacture a finish, export or
    creative approval. No native command is replayed.
    """
    artifacts = Path(artifacts)
    ledger_path = artifacts / "native-journal.jsonl"
    if not ledger_path.is_file():
        return {"partial_journal_present": False,
                "partial_journal_structurally_verified": False}
    try:
        checked = audit_native_journal(
            read_native_journal(ledger_path),
            host_tool_access=host_tool_access,
            expected_required_evidence=expected_required_evidence,
            host_content_revision_tools=host_content_revision_tools)
        if (not isinstance(checked, dict) or
                checked.get("journal_chain_structurally_valid") is not True):
            raise ValueError("Partial native journal auditor did not verify its chain")
    except Exception as exc:
        result = {
            "partial_journal_present": True,
            "partial_journal_structurally_verified": False,
            "partial_journal_audit_error_type": type(exc).__name__,
            "technical_trial_completed": False,
        }
        (artifacts / "journal-audit-partial.json").write_text(
            json.dumps(result, indent=2))
        return result
    result = {
        **checked,
        "partial_journal_present": True,
        "partial_journal_structurally_verified": True,
        "technical_trial_completed": False,
        "artistic_quality_approved": False,
        "incomplete_trial_no_native_write_replay": True,
    }
    (artifacts / "journal-audit-partial.json").write_text(
        json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'runtime', 'artifacts'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--xvfb-binary', default='/usr/bin/Xvfb')
    parser.add_argument('--display', default='127.0.0.1:95')
    parser.add_argument('--model-lock', type=Path,
        default=ROOT / 'engines/velorn/local-model-trial.lock.json',
        help='Local pinned model manifest; default remains the verified 2B baseline')
    args = parser.parse_args()
    args.source, args.runtime, args.artifacts = (getattr(args, name).resolve() for name in ('source', 'runtime', 'artifacts'))
    args.artifacts.mkdir(parents=True, exist_ok=False)
    args.runtime.mkdir(parents=True, exist_ok=True)
    evidence = {'schema': 1, 'technical_trial_completed': False, 'artistic_quality_approved': False,
                'native_field_complete': False, 'script_supplied_editor_mutations': 0,
                'cpu_count': os.cpu_count(), 'model_ram_independently_measured': False}
    process = None
    lock = json.loads(args.model_lock.resolve().read_text())
    if lock.get('model', {}).get('license') != 'Apache-2.0':
        raise ValueError('Candidate model needs an explicit compatible model-weight license')
    try:
        if os.geteuid() == 0:
            raise RuntimeError('Live editor trial requires ordinary non-root Chromium sandbox execution')
        evidence['pinned_inputs'] = lock
        archive = download(lock['runtime']['archive'], args.runtime)
        files = {entry['kind']: download(entry, args.runtime) for entry in lock['model']['files']}
        # A candidate pointer published by a third party is a *proposed*
        # hash until this process actually rehashes the downloaded bytes.
        evidence['actual_model_file_sha256_verified'] = {
            kind: {'sha256': sha(path), 'bytes': path.stat().st_size}
            for kind, path in files.items()}
        with tarfile.open(archive) as source:
            source.extractall(args.runtime, filter='data')
        binary = args.runtime / lock['runtime']['binary_relative_path']
        command = [str(binary)] + [str(files['model']) if value == 'MODEL_PATH' else
            str(files['vision_projector']) if value == 'MMPROJ_PATH' else value for value in lock['server']['args']]
        # Fail on an occupied local endpoint instead of connecting to an unrelated model.
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 8080))
        with (args.artifacts / 'model-server.log').open('w') as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            started = time.monotonic()
            while True:
                if process.poll() is not None:
                    raise RuntimeError('Actual model runtime exited; inspect preserved server log')
                try:
                    with urlopen('http://127.0.0.1:8080/health', timeout=2) as response:
                        if response.status == 200:
                            break
                except OSError:
                    pass
                if time.monotonic() - started > 120:
                    raise TimeoutError('Actual model load exceeded host budget')
                time.sleep(.25)
            evidence['measured_model_start_seconds'] = time.monotonic() - started
            evidence.update(asyncio.run(trial(args, lock, args.artifacts, command)))
    except BaseException as exc:
        evidence.update(error_type=type(exc).__name__, error=str(exc)[:2000])
        raise
    finally:
        if process is not None:
            # Read /proc while this exact child is still owned and alive.
            # Successful parsing is independent observation, not the model's
            # claimed memory consumption or a cross-process system peak.
            if process.poll() is None:
                peak = read_live_linux_model_peak_rss(process.pid)
                if peak is not None:
                    evidence['model_server_process_peak_rss_bytes'] = peak
                    evidence['model_ram_independently_measured'] = True
                    evidence['model_ram_measurement_scope'] = (
                        'Linux /proc/PID/status VmHWM of this model-server PID only; '
                        'not editor+OS total or cgroup peak')
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill(); process.wait()
        for log in (args.runtime / 'editor-state').glob('session-*/**/*.log'):
            target = args.artifacts / 'engine-logs' / log.relative_to(args.runtime / 'editor-state')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(log.read_bytes()[-1024 * 1024:])
        (args.artifacts / 'evidence.json').write_text(json.dumps(evidence, indent=2, allow_nan=False))
    if not evidence['technical_trial_completed']:
        raise RuntimeError('Model trial did not reach edit/observe/revise/export acceptance; no fallback used')


if __name__ == '__main__':
    main()
