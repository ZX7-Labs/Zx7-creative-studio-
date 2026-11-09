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
from studio_next.native_editor_source_pin import (pinned_electron_marker_previews, pinned_electron_asset_placement_previews, pinned_electron_clip_edit_previews, pinned_electron_timeline_frame_previews)
from studio_next.native_creative_audit import audit_native_journal, read_native_journal
from studio_next.native_render_evidence import REVIEWED_NATIVE_EVIDENCE, destination_digest
from studio_next.providers import LocalModelSettings
from studio_next.local_native_structured_model import LocalNativeStructuredCreativeModel
from studio_next.capability_gateway import CapabilityGateway
from studio_next.capability_mcp_session import CapabilityGatewayMcpSession
from studio_next.capability_session_budget import CapabilitySessionBudget


async def admit_local_native_model_session(native_session, host_grants, *,
                                           max_model_turns: int):
    """Admit a model through one connected, trusted, budgeted BODY source.

    Calls and writes are actual gateway *reservations*. They do not represent
    LLM token accounting, paid costs or independently verified native edits.
    The model cannot choose the host grants or the gateway itself.
    """
    if (type(max_model_turns) is not int or
            not 1 <= max_model_turns <= 1000):
        raise ValueError("Trial model turn budget must be a bounded positive integer")
    budget = CapabilitySessionBudget(
        max_calls=max_model_turns * 12, max_writes=max_model_turns)
    gateway = CapabilityGateway(
        {"editor": (native_session, host_grants)}, session_budget=budget)
    await gateway.refresh()
    admitted = CapabilityGatewayMcpSession(gateway, "editor")
    return admitted, gateway


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
    def requires_indexed_native_function_contracts(self):
        return getattr(self.model, "requires_indexed_native_function_contracts", False)

    @property
    def last_call_usage(self):
        return self.model.last_call_usage

    def infer(self, context, images=()):
        started = time.monotonic()
        # The actual local trial uses the SAME host-current dynamic native
        # schema adapter as the production native-model client. Previously
        # this wrapper mutated shared sampling configuration and independently
        # constructed the grammar, risking drift after every native read/write.
        # The passive recorder never selects actions or alters model policy.
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
    # Import is a real installed native operation that may establish a
    # nonempty project asset inventory AFTER the project actually opens.
    # The presence of staged media alone cannot establish that fact.
    return {"create_project": ["project_open"],
            "import_asset_from_path": ["project_assets_available"],
            # These operations MAY populate an actual timeline, but a new
            # content clip is not a saved/visible original-footage proof.
            "add_asset_to_timeline": ["timeline_clips_available"],
            "add_assets_to_timeline": ["timeline_clips_available"]}


async def trial(args, lock, artifacts, command):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    projects, staging, outputs = (artifacts / name for name in ('projects', 'staging', 'outputs'))
    for root in (projects, staging, outputs):
        root.mkdir()
    initial_project_effects = fresh_trial_project_open_effects(projects)
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
        'Keep the export settings identical for both versions so the editorial change can be compared. '
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
    model = RecordedModel(LocalNativeStructuredCreativeModel(LocalModelSettings(
        model_id=lock['server']['alias'], base_url='http://127.0.0.1:8080',
        timeout_seconds=args.model_timeout),
        system_prompt=NATIVE_CREATIVE_SYSTEM), artifacts)
    # This mapping originates in the trusted host config, not the
    # replaceable neural model. Only READ errors may be safely corrected.
    from studio_next.native_editor_session import native_session_grants
    host = native_session_grants(config, args.source)
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
    completion_evidence = REVIEWED_NATIVE_EVIDENCE
    with (artifacts / 'editor-stderr.log').open('w') as log:
        async with stdio_client(StdioServerParameters(command='node', args=params, cwd=ROOT), errlog=log) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=180) as session:
                await session.initialize()
                # Model-originated READs, WRITE proposals and the controller's
                # mandatory readback observations all traverse ONE host-owned
                # grant/ABI authority. Preserve the editor's original native
                # schemas; the model never receives an unmediated MCP session.
                # This is a bounded CPU *trial* admission budget, not an LLM
                # token/price measurement or a 24-hour production quota.
                max_model_turns = 48
                admitted_model_session, gateway = (
                    await admit_local_native_model_session(
                        session, host, max_model_turns=max_model_turns))
                try:
                    outcome = await asyncio.wait_for(NativeCreativeControl(
                    admitted_model_session, model, max_turns=max_model_turns,
                    receipt_path=artifacts / 'native-journal.jsonl',
                    host_tool_access=host, catalog_mode="indexed",
                    host_pre_dispatch_rejections=True,
                    host_preconditions={
                        "import_asset_from_path": ["project_open"],
                        "add_asset_to_timeline": [
                            "project_open", "project_assets_available"],
                        "add_assets_to_timeline": [
                            "project_open", "project_assets_available"],
                        # The second physical 2B trial attempted a native
                        # replacement after an acknowledged create but before
                        # the project was independently observable. A write
                        # with no native timeline must not be dispatched;
                        # fail preflight and let the model re-inspect reality.
                        "replace_clip_with_asset": [
                            "project_open", "project_assets_available",
                            "timeline_clips_available"],
                        "duplicate_clip": [
                            "project_open", "timeline_clips_available"],
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
                    # The pinned *Electron MCP* marker API, not the
                    # downstream renderer handler, guarantees that these
                    # previewOnly:true calls return a read-only top-level
                    # preview before a mutating performAction is reached.
                    host_verified_top_level_preview_tools=(
                        pinned_electron_marker_previews(args.source, host) +
                        pinned_electron_asset_placement_previews(args.source, host) +
                        pinned_electron_clip_edit_previews(args.source, host)),
                    # Technical owner acceptance facts, NOT an editing plan.
                    # Failed model claims cannot end the trial before actual
                    # native activity, source-verified export and visual sensing.
                    host_verified_timeline_preview_tools=(
                        pinned_electron_timeline_frame_previews(args.source, host)),
                    required_evidence=completion_evidence,
                    host_content_revision_tools=host_content_revision_tools).run(brief),
                    timeout=args.trial_timeout)
                finally:
                    # Admitted calls are not evidence of real native commits;
                    # write bounded model-neutral accounting even on failure.
                    (artifacts / "host-native-admission.json").write_text(
                        json.dumps(gateway.host_budget_evidence(), indent=2))
    audit = audit_native_journal(
        read_native_journal(artifacts / 'native-journal.jsonl'),
        host_pre_dispatch_rejections=True,
        host_verified_preview_error_tools=(
            pinned_electron_marker_previews(args.source, host) +
            pinned_electron_asset_placement_previews(args.source, host) +
            pinned_electron_clip_edit_previews(args.source, host)),
        host_tool_access=host, expected_required_evidence=completion_evidence,
        host_content_revision_tools=host_content_revision_tools)
    (artifacts / 'journal-audit.json').write_text(json.dumps(audit, indent=2))
    actual_images = len(list((artifacts / 'observations').glob('*.png')))
    movies = {}
    for path in outputs.glob('*.mp4'):
        movies.setdefault(sha(path), set()).add(path.resolve())
    inference = {record['context']['turn']: record
        for record in map(json.loads, (artifacts / 'inference-transcript.jsonl').read_text().splitlines())
        if 'decision' in record}
    observed_sources, revisions, last_revision, last_save, revised_exports = set(), 0, -1, -1, []
    sources_before_revision = set()
    exported_after_revision = set()
    for index, event in enumerate(outcome['events']):
        if event.get('kind') != 'native_tool_result':
            continue
        if event.get('tool') == 'save_project':
            last_save = index
        if observed_sources and event.get('tool') in content_tools:
            revisions += 1
            last_revision = index
            sources_before_revision = observed_sources.copy()
            revised_exports = []
            exported_after_revision = set()
        if last_revision >= 0 and event.get('tool') == 'export_timeline':
            output_path = inference[event['turn']]['decision']['arguments']['inputs'].get('outputPath')
            if isinstance(output_path, str):
                exported_after_revision.add(Path(output_path).resolve())
        verified = event.get('independently_verified_export_sha256')
        if (last_revision >= 0 and verified and verified not in observed_sources
                and movies.get(verified, set()) & exported_after_revision):
            revised_exports.append(verified)
        delivered_images = inference.get(event['turn'] + 1, {}).get('image_sha256', [])
        if (event.get('observed_export_sha256') and
                any(digest in delivered_images for digest in event.get('image_sha256', []))):
            observed_sources.add(event['observed_export_sha256'])
    # Use the same source custody and timed-picture checks as the hosted trial.
    from scripts.run_nvidia_native_trial import (
        decode_trial_export, trial_delivery_profile_compliant,
        trial_picture_changed, verify_saved_native_trial,
    )
    try:
        saved_native = verify_saved_native_trial(artifacts, source_ledger=source_assets, max_clip_duration=8)
    except (ValueError, OSError) as exc:
        saved_native = {"native_saved_project_verified": False,
                        "native_saved_project_rejection_type": type(exc).__name__}
    else:
        saved_native["native_saved_project_verified"] = True
    native_projects = list(projects.glob('*/project.comfystudio')) if saved_native["native_saved_project_verified"] else []
    # The same observed/exported digest may appear at more than one path. Pick
    # one deterministically and decode it at most once for this comparison.
    changed_presentation = False
    reviewed_pair_delivery_profile_compliant = False
    presentation_rejection = None
    picture_profiles = None
    pair = audit["reviewed_native_render_pair"]
    if (pair and pair[1]["timeline_sha256"] == saved_native.get("saved_native_timeline_sha256") and
            pair[0]["export_sha256"] in sources_before_revision and pair[1]["export_sha256"] in revised_exports):
        try:
            paths = [{path for path in movies.get(item["export_sha256"], ())
                      if destination_digest(str(path)) == item["destination_sha256"]}
                     for item in pair]
            if all(len(matches) == 1 for matches in paths):
                before, after = (decode_trial_export(next(iter(matches)),
                    expected_sha256=item["export_sha256"], max_frames=960)
                    for item, matches in zip(pair, paths, strict=True))
                picture_profiles = [before.picture_profile, after.picture_profile]
                reviewed_pair_delivery_profile_compliant = (
                    trial_delivery_profile_compliant(before, max_seconds=8) and
                    trial_delivery_profile_compliant(after, max_seconds=8))
                changed_presentation = trial_picture_changed(before, after)
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            presentation_rejection = type(exc).__name__
    passed = (outcome['status'] == 'model_finished_unverified' and actual_images > 0
              and revisions > 0 and last_save > last_revision and bool(native_projects)
              and bool(revised_exports) and changed_presentation and
              reviewed_pair_delivery_profile_compliant)
    return {'technical_trial_completed': passed, 'model_status': outcome['status'],
            'reviewed_pair_synthetic_delivery_profile_compliant':
                reviewed_pair_delivery_profile_compliant,
            'image_inputs_actually_sent': actual_images, 'content_mutations_after_observation': revisions,
            'decoded_frame_sequence_changed': changed_presentation,
            'decoded_frame_sequence_rejection_type': presentation_rejection,
            'decoded_reviewed_picture_profiles': picture_profiles,
            'verified_exports_after_final_revision': revised_exports,
            'saved_native_projects': [str(path.relative_to(artifacts)) for path in native_projects],
            'saved_native_source_evidence': saved_native, 'audit': audit,
            'acceptance_note': 'Source-chain and model-operation evidence only, not artistic acceptance'}


def build_trial_parser():
    """Bound local inference and editor wall-clock budgets without relaxing source grants."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'runtime', 'artifacts'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--xvfb-binary', default='/usr/bin/Xvfb')
    parser.add_argument('--display', default='127.0.0.1:95')
    parser.add_argument('--model-timeout', type=int, choices=(300, 480), default=300,
                        help='Seconds for one local model response')
    parser.add_argument('--trial-timeout', type=int, choices=(2400, 7200, 13200), default=2400,
                        help='Bounded seconds for the full model/editor loop (220 min opt-in ceiling)')
    parser.add_argument('--model-lock', type=Path,
        default=ROOT / 'engines/velorn/local-model-trial.lock.json',
        help='Local pinned model manifest; default remains the verified 2B baseline')
    return parser


def main():
    args = build_trial_parser().parse_args()
    args.source, args.runtime, args.artifacts = (getattr(args, name).resolve() for name in ('source', 'runtime', 'artifacts'))
    args.artifacts.mkdir(parents=True, exist_ok=False)
    args.runtime.mkdir(parents=True, exist_ok=True)
    evidence = {'schema': 1, 'technical_trial_completed': False, 'artistic_quality_approved': False,
                'native_field_complete': False, 'script_supplied_editor_mutations': 0,
                'cpu_count': os.cpu_count(), 'model_ram_independently_measured': False,
                'model_timeout_seconds': args.model_timeout, 'trial_timeout_seconds': args.trial_timeout}
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
