"""Rights-attested CGI: PBR maps, product geometry and authored camera motion.

This adapter freezes every image/GLB before Blender runs. The artist chooses
the complete scene; there is no product, lighting or advertising template.
"""
from __future__ import annotations
import json,os,tempfile
from pathlib import Path
from .blender_scene import validate_blender_shot,referenced_scene_assets
from .composite_mix import _exact_media,sealed_attested_original
from .media_vault import MediaVault,sha256_file,verify_media_container,canonical_source_attestations
from .native_body_engines import render_original_blender
from .production_qc import full_decode_inspection


def render_cgi_plan(plan_file,workspace,vault_root,output):
    root=Path(workspace).resolve();plan_file=Path(plan_file).resolve();output=Path(output).resolve()
    if not plan_file.is_relative_to(root) or not plan_file.is_file() or not output.is_relative_to(root) or output.exists() or output.suffix.lower()!='.mp4':
        raise ValueError('CGI requires an original plan and a new workspace MP4')
    plan_hash=sha256_file(plan_file);plan=json.loads(plan_file.read_text())
    if set(plan)!={'scene','assets'} or not isinstance(plan['scene'],dict) or not isinstance(plan['assets'],list):
        raise ValueError('CGI plan requires a scene and exact named asset custody')
    scene=plan['scene'];assets=plan['assets'];named={};vault=MediaVault(vault_root)
    for item in assets:
        if not isinstance(item,dict) or set(item)!={'name','media'} or not isinstance(item['name'],str):
            raise ValueError('Each CGI asset needs a unique local name and source attestation')
        name=item['name']
        if not name or name in named or '\\' in name or ':' in name or name.startswith('/') or any(not p or p.startswith('.') for p in name.split('/')):
            raise ValueError('Unsafe or duplicate CGI asset name')
        media=item['media'];path=_exact_media(media,vault,root,need='CGI asset')
        record=vault.inspect(media['asset_id'],attestation_id=media['attestation_id'])
        allowed={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.glb':'model/gltf-binary'}
        if allowed.get(Path(name).suffix.lower())!=record['mime']:
            raise ValueError('CGI asset name does not match its real licensed media type')
        verify_media_container(path,record['mime'])
        named[name]=(media,path,record)
    if referenced_scene_assets(scene)!=set(named):
        raise ValueError('Every referenced CGI texture/model requires exact declared custody; no unused hidden assets')
    with tempfile.TemporaryDirectory(prefix='.zx7-cgi-owned-',dir=root) as temp:
        private=Path(temp);asset_root=private/'assets';asset_root.mkdir();snapshots={}
        for name,(media,path,record) in named.items():
            frozen=sealed_attested_original(vault,media['asset_id'],media['attestation_id'],private,snapshots)
            target=asset_root/name;target.parent.mkdir(parents=True,exist_ok=True);os.link(frozen,target)
        validate_blender_shot(scene,verified_assets_root=asset_root)
        for obj in scene['objects']:
            if obj['type']=='licensed_glb':
                record=named[obj['asset']][2]
                if obj['rights']!=record['rights_attestations'][0]['rights']:
                    raise ValueError('GLB scene label differs from the authenticated source rights')
        frozen_scene=private/'scene.json';frozen_scene.write_text(json.dumps(scene))
        encoded=private/'cgi.mp4'
        native=render_original_blender(frozen_scene,encoded,trusted_asset_root=asset_root)
        check=full_decode_inspection(encoded,expected={'width':scene['width'],'height':scene['height'],
            'duration_seconds':scene['frames']/scene['fps'],'require_audio':False})
        if not check['technical_delivery_verified']:raise RuntimeError('CGI output failed actual decoder')
        if sha256_file(plan_file)!=plan_hash:raise ValueError('CGI direction changed during rendering')
        for name,(media,path,record) in named.items():
            if sha256_file(path)!=media['asset_id'] or sha256_file(asset_root/name)!=media['asset_id']:
                raise ValueError('Original CGI source or sealed decoder asset changed')
            vault.inspect(media['asset_id'],attestation_id=media['attestation_id'])
        output.parent.mkdir(parents=True,exist_ok=True)
        with encoded.open('rb') as stream:os.fsync(stream.fileno())
        os.link(encoded,output)
    return {'path':str(output),'sha256':sha256_file(output),'original_plan_sha256':plan_hash,
        'source_assets':len(named),'sealed_source_custody_during_render':True,
        'source_attestations':canonical_source_attestations([
            {key:media[key] for key in ('asset_id','attestation_id')}
            for media,_,_ in named.values()]),
        'actual_native_cgi_rendered':True,'complete_decoder_verified':True,
        'native_controls':native['native_controls'],
        'aesthetic_quality_approved':False}
