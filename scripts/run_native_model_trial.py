"""Bounded real CPU-model/native-editor trial. Never supplies editing actions.

The generated media are neutral owned test inputs, not a prescribed edit. The
identified neural model chooses every editor mutation. This does not certify
professional creative quality, source rights beyond these fixtures or isolation.
"""
import argparse
import asyncio
import hashlib
import json
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
from studio_next.native_camera_seed import stage_attested_camera, verify_native_original_timeline


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
    def __init__(self, model, artifacts, *, initial_source_picture=None):
        self.model, self.settings, self.artifacts = model, model.settings, artifacts
        self.initial_source_picture = initial_source_picture
        self.turn = 0

    @property
    def last_call_usage(self):
        return self.model.last_call_usage

    def infer(self, context, images=()):
        # Before the first model choice, show independently decoded ORIGINAL
        # camera pixels. These are not a verified post-edit export observation.
        seed_added = self.turn == 0 and self.initial_source_picture is not None
        if seed_added:
            images = (("image/png", self.initial_source_picture.read_bytes()),) + tuple(images)
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
            # Original-camera seed is NOT an observed exported movie frame.
            folder = 'source-observations' if seed_added and index == 0 else 'observations'
            path = self.artifacts / folder / f'{self.turn}-{index}.png'
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
    # Source bootstrap never authors timeline edits. The real local model still
    # chooses every native mutation through granted tools.
    source_assets = []
    camera_seed = None
    if args.camera_video is not None:
        if args.camera_rights is None:
            raise ValueError("An explicit attested camera-rights manifest is required")
        camera_seed = stage_attested_camera(
            args.camera_video, args.camera_rights, staging, artifacts)
        source_assets.append({
            "path": camera_seed["path"],
            "sha256": camera_seed["sha256"],
            "rights": camera_seed["rights"],
            "duration_seconds": camera_seed["source_duration_seconds"],
            "source_has_audio": camera_seed["source_has_audio"],
            "camera_original": True,
        })
    else:
        if args.camera_rights is not None:
            raise ValueError("Rights manifest without source video is invalid")
        # Original neutral technical fixture, unaffected by camera mode.
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
    if camera_seed is not None:
        brief = (
            "Edit this video. Use your independent creative judgment and "
            "the actual camera source, not a prescribed storyboard. The "
            "attached source-grounded frames are only still-image observations, "
            "not continuous motion or audio understanding. Create a native "
            "editable project, export and verify a real video, inspect genuine "
            "export pixels, make a model-chosen revision and save the new native "
            "version. Preserve the original camera recording, which has "
            "source-declared CC0 metadata but no independent legal clearance. "
            "This CPU-only technical experiment limits output to eight seconds "
            "and 640x360: physical budget, never a style or product ceiling. "
            "The model cannot claim to hear raw video audio from image evidence. "
            "After media import, inspect real native asset IDs: paths and MCP "
            "tool IDs are NOT media asset IDs. "
            f"Projects folder: {projects}. Output folder: {outputs}. "
            "Available camera source: " + json.dumps(source_assets))
    else:
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
            'Staged source paths are NOT imported native assets; obtain actual '
            'editor asset IDs by inspecting permitted native tools after the '
            'import operation. An MCP tool ID is never a media asset ID. '
            'Available source assets: ' + json.dumps(source_assets))
    (artifacts / 'brief.txt').write_text(brief)
    params = [str(ROOT / 'engines/velorn/mcp.mjs'), '--source', str(args.source),
              '--config', str(config_path), '--state', str(args.runtime / 'editor-state'),
              '--python', sys.executable, '--xvfb-binary', args.xvfb_binary, '--display', args.display]
    model = RecordedModel(LocalCreativeModel(LocalModelSettings(
        model_id=lock['server']['alias'], base_url='http://127.0.0.1:8080', timeout_seconds=300),
        system_prompt=NATIVE_CREATIVE_SYSTEM), artifacts,
        initial_source_picture=(
            Path(camera_seed["camera_preview_path"]) if camera_seed else None))
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
                outcome = await asyncio.wait_for(NativeCreativeControl(session, model, max_turns=48,
                    receipt_path=artifacts / 'native-journal.jsonl',
                    host_tool_access=host, catalog_mode="indexed",
                    host_preconditions={
                        "import_asset_from_path": ["project_open"],
                        # Native media placement must be source-bound to
                        # independently read back project imports, not staged
                        # basenames or model-invented asset IDs.
                        "add_asset_to_timeline": ["project_open", "assets_present"],
                        "add_assets_to_timeline": ["project_open", "assets_present"],
                        # The second physical 2B trial attempted a native
                        # replacement after an acknowledged create but before
                        # the project was independently observable. A write
                        # with no native timeline must not be dispatched;
                        # fail preflight and let the model re-inspect reality.
                        "replace_clip_with_asset": ["project_open", "assets_present"],
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
        if last_revision >= 0 and event.get('tool') == 'export_timeline':
            output_path = decisions[event['turn']]['arguments']['inputs'].get('outputPath')
            if isinstance(output_path, str):
                exported_after_revision.add(Path(output_path).resolve())
        verified = event.get('independently_verified_export_sha256')
        if (last_revision >= 0 and verified and verified not in observed_sources
                and movies.get(verified, set()) & exported_after_revision):
            revised_exports.append(verified)
        if event.get('image_sha256') and event.get('observed_export_sha256'):
            observed_sources.add(event['observed_export_sha256'])
    native_projects = [path for path in projects.glob('*/project.comfystudio')
        if any(timeline.get('clips') for timeline in json.loads(path.read_text()).get('timelines', []))]
    # A model's textual claim of importing the original is not evidence.
    # Re-open saved native documents and check their actual referenced bytes.
    camera_original_saved = False
    camera_original_on_timeline = False
    camera_native_evidence = []
    if camera_seed is not None:
        for native_path in native_projects:
            checked = verify_native_original_timeline(native_path, camera_seed["sha256"])
            camera_native_evidence.append(checked)
            camera_original_saved |= checked["original_camera_bytes_preserved"]
            camera_original_on_timeline |= checked["original_on_saved_native_timeline"]
    def decoded_frames(path):
        raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path),
            '-map', '0:v:0', '-f', 'framemd5', '-'], timeout=60).decode()
        return [line.split(',')[-1].strip() for line in raw.splitlines() if line and not line.startswith('#')]
    changed_pixels = any(decoded_frames(next(iter(movies[before]))) != decoded_frames(next(iter(movies[after])))
        for before in observed_sources for after in revised_exports if before in movies and after in movies)
    passed = (outcome['status'] == 'model_finished_unverified' and actual_images > 0
              and revisions > 0 and last_save > last_revision and bool(native_projects)
              and bool(revised_exports) and changed_pixels
              and (camera_seed is None or (camera_original_saved and camera_original_on_timeline)))
    return {'technical_trial_completed': passed, 'model_status': outcome['status'],
            'native_original_camera_file_preserved': (
                camera_original_saved if camera_seed is not None else None),
            'camera_mode_used': camera_seed is not None,
            'original_camera_on_saved_native_timeline': (
                camera_original_on_timeline if camera_seed is not None else None),
            'native_camera_project_verification': camera_native_evidence,
            'image_inputs_actually_sent': actual_images, 'content_mutations_after_observation': revisions,
            'decoded_frame_sequence_changed': changed_pixels,
            'verified_exports_after_final_revision': revised_exports,
            'saved_native_projects': [str(path.relative_to(artifacts)) for path in native_projects], 'audit': audit,
            'acceptance_note': 'Source-chain and model-operation evidence only, not artistic acceptance'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'runtime', 'artifacts'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--xvfb-binary', default='/usr/bin/Xvfb')
    parser.add_argument('--display', default='127.0.0.1:95')
    parser.add_argument('--camera-video', type=Path, default=None,
        help='Optional exact CC0-attested unedited original camera source')
    parser.add_argument('--camera-rights', type=Path, default=None,
        help='Rights/source SHA evidence for --camera-video')
    parser.add_argument('--model-lock', type=Path,
        default=ROOT / 'engines/velorn/local-model-trial.lock.json',
        help='Local pinned model manifest; default remains the verified 2B baseline')
    args = parser.parse_args()
    if (args.camera_video is None) != (args.camera_rights is None):
        parser.error('--camera-video and --camera-rights must be provided together')
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
