"""Real planar tracking/corner-pin compositing on attested original footage.

SIFT + RANSAC estimates an independent reference-to-frame homography. A lost
track fails; it never becomes a static graphic or a fabricated successful shot.
Optional original foreground masks preserve real occluders. This is 8-bit SDR
planar VFX, not 3D camera solving, automatic person roto or scene-linear EXR.
"""
from __future__ import annotations
import json,math,os,subprocess,tempfile
from pathlib import Path
from .media_vault import MediaVault,sha256_file,canonical_source_attestations
from .composite_mix import _exact_media,sealed_attested_original,_decoded_source_duration
from .precision_retime import _source_timebase
from .body_color_pipeline import _actual_bt709_source
from .production_qc import full_decode_inspection


def validate_tracking_settings(settings):
    if not isinstance(settings,dict) or set(settings)!={'max_features','min_matches','min_inlier_ratio','ransac_pixels','max_reprojection_error'}:
        raise ValueError('Explicit feature, inlier and reprojection tracking controls required')
    for name,low,high in [('max_features',32,20000),('min_matches',8,2000)]:
        if type(settings[name]) is not int or not low<=settings[name]<=high:raise ValueError('Invalid '+name)
    if settings['min_matches']>settings['max_features']:raise ValueError('Not enough allowed features for requested matches')
    for name,low,high in [('min_inlier_ratio',.1,1),('ransac_pixels',.1,30),('max_reprojection_error',.1,30)]:
        x=settings[name]
        if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or not low<=x<=high:raise ValueError('Invalid '+name)


def checked_quad(quad,width,height,*,inside=False):
    import cv2,numpy as np
    q=np.asarray(quad,dtype=np.float64)
    if q.shape!=(4,2) or not np.isfinite(q).all() or np.max(np.abs(q))>1e6:
        raise ValueError('Four finite ordered planar corners required')
    if not cv2.isContourConvex(q.astype(np.float32)) or abs(cv2.contourArea(q.astype(np.float32)))<16:
        raise ValueError('Planar corners fold, cross or have no area')
    if inside and ((q[:,0]<0).any() or (q[:,0]>=width).any() or (q[:,1]<0).any() or (q[:,1]>=height).any()):
        raise ValueError('Reference planar corners must lie in the first original frame')
    return q


class PlanarTracker:
    def __init__(self,reference,quad,settings):
        import cv2,numpy as np
        validate_tracking_settings(settings);self.settings=settings;self.quad=checked_quad(quad,reference.shape[1],reference.shape[0],inside=True)
        mask=np.zeros(reference.shape[:2],np.uint8);cv2.fillConvexPoly(mask,self.quad.astype(np.int32),255)
        self.sift=cv2.SIFT_create(nfeatures=settings['max_features'])
        self.keys,self.descriptors=self.sift.detectAndCompute(cv2.cvtColor(reference,cv2.COLOR_BGR2GRAY),mask)
        if self.descriptors is None or len(self.keys)<settings['min_matches']:raise ValueError('Original plane has insufficient texture to track')
        self.matcher=cv2.BFMatcher(cv2.NORM_L2)

    def locate(self,frame):
        import cv2,numpy as np
        keys,desc=self.sift.detectAndCompute(cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY),None)
        if desc is None or len(keys)<2:raise RuntimeError('Planar track lost: no measured current features')
        pairs=self.matcher.knnMatch(self.descriptors,desc,k=2)
        good=[a for pair in pairs if len(pair)==2 for a,b in [pair] if a.distance<.75*b.distance]
        if len(good)<self.settings['min_matches']:raise RuntimeError('Planar track lost: insufficient independent matches')
        src=np.float32([self.keys[m.queryIdx].pt for m in good]);dst=np.float32([keys[m.trainIdx].pt for m in good])
        H,mask=cv2.findHomography(src,dst,cv2.RANSAC,self.settings['ransac_pixels'])
        if H is None or mask is None or not np.isfinite(H).all():raise RuntimeError('Planar track lost: no finite homography')
        keep=mask.ravel().astype(bool);count=int(keep.sum());ratio=count/len(good)
        if count<self.settings['min_matches'] or ratio<self.settings['min_inlier_ratio']:raise RuntimeError('Planar track lost: weak geometric agreement')
        predicted=cv2.perspectiveTransform(src.reshape(-1,1,2),H).reshape(-1,2)
        error=float(np.sqrt(np.mean(np.sum((predicted[keep]-dst[keep])**2,axis=1))))
        if error>self.settings['max_reprojection_error']:raise RuntimeError('Planar track lost: reprojection error exceeds authored tolerance')
        corners=cv2.perspectiveTransform(self.quad.reshape(-1,1,2),H).reshape(4,2)
        checked_quad(corners,frame.shape[1],frame.shape[0])
        if cv2.contourArea(corners.astype(np.float32),oriented=True)*cv2.contourArea(self.quad.astype(np.float32),oriented=True)<=0:
            raise RuntimeError('Planar track flipped its surface orientation')
        return corners,{'matches':len(good),'inliers':count,'inlier_ratio':ratio,'reprojection_error_pixels':error}


def composite_corner_pin(frame,overlay,quad,opacity,foreground=None):
    import cv2,numpy as np
    h,w=frame.shape[:2];oh,ow=overlay.shape[:2]
    if overlay.ndim!=3 or overlay.shape[2]!=4 or min(oh,ow)<2:raise ValueError('Corner pin requires actual RGBA artwork')
    source=np.float32([[0,0],[ow-1,0],[ow-1,oh-1],[0,oh-1]])
    transform=cv2.getPerspectiveTransform(source,np.float32(quad))
    rgba=overlay.astype(np.float32)/255;rgba[:,:,:3]*=rgba[:,:,3:4]
    warped=cv2.warpPerspective(rgba,transform,(w,h),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
    amount=np.full((h,w,1),opacity,np.float32)
    if foreground is not None:
        if foreground.shape!=(h,w):raise ValueError('Foreground matte differs from original picture geometry')
        amount*=1-foreground.astype(np.float32)[:,:,None]/255
    alpha=warped[:,:,3:4]*amount
    mixed=warped[:,:,:3]*amount+frame.astype(np.float32)/255*(1-alpha)
    return np.rint(np.clip(mixed,0,1)*255).astype(np.uint8)


def render_planar_insert(plan_file,workspace,vault_root,output):
    import cv2,numpy as np
    root=Path(workspace).resolve();document=Path(plan_file).resolve();output=Path(output).resolve()
    if not document.is_relative_to(root) or not document.is_file() or not output.is_relative_to(root) or output.exists() or output.suffix.lower()!='.mp4':
        raise ValueError('Planar VFX requires an owned plan and new workspace output')
    plan_hash=sha256_file(document);plan=json.loads(document.read_text())
    if not isinstance(plan,dict) or not {'media','overlay','quad','tracking','opacity','audio'}.issubset(plan) or set(plan)-{'media','overlay','quad','tracking','opacity','audio','foreground'}:
        raise ValueError('Planar VFX requires original footage, art, corners and explicit tracking controls')
    validate_tracking_settings(plan['tracking'])
    if type(plan['opacity']) not in (float,int) or not math.isfinite(plan['opacity']) or not 0<=plan['opacity']<=1:raise ValueError('Invalid overlay opacity')
    if plan['audio'] not in ('preserve_source','intentional_silence'):raise ValueError('Choose original sound preservation or intentional silence')
    vault=MediaVault(vault_root);originals=[]
    for field in ('media','overlay'):
        p=_exact_media(plan[field],vault,root,need=field);originals.append((p,plan[field]))
    source,art=originals[0][0],originals[1][0]
    if vault.inspect(plan['media']['asset_id'],attestation_id=plan['media']['attestation_id'])['mime']!='video/mp4' or vault.inspect(plan['overlay']['asset_id'],attestation_id=plan['overlay']['attestation_id'])['mime']!='image/png':
        raise ValueError('Planar VFX needs decoded MP4 footage and PNG art')
    _actual_bt709_source(source);fps,count=_source_timebase(source);duration=float(count/fps)
    if plan['audio']=='preserve_source' and _decoded_source_duration(source,'audio')+0.015<duration:raise ValueError('Original sound does not cover the authored footage')
    foreground=plan.get('foreground')
    if foreground is not None:
        if not isinstance(foreground,dict) or set(foreground)!={'media','kind'} or foreground['kind'] not in ('still_image','video'):raise ValueError('Foreground requires an explicit attested image or video matte')
        p=_exact_media(foreground['media'],vault,root,need='foreground matte');originals.append((p,foreground['media']))
        mime=vault.inspect(foreground['media']['asset_id'],attestation_id=foreground['media']['attestation_id'])['mime']
        if mime!=('image/png' if foreground['kind']=='still_image' else 'video/mp4'):raise ValueError('Matte kind differs from actual source')
        if foreground['kind']=='video' and _source_timebase(p)!=(fps,count):raise ValueError('Moving matte clock differs from original footage')
    metrics=[]
    with tempfile.TemporaryDirectory(prefix='.zx7-planar-owned-',dir=root) as temp:
        private=Path(temp);snapshots={};frozen=[]
        for p,media in originals:frozen.append(sealed_attested_original(vault,media['asset_id'],media['attestation_id'],private,snapshots))
        capture=cv2.VideoCapture(str(frozen[0]));mask_capture=None
        try:
            ok,first=capture.read()
            if not ok:raise ValueError('Cannot decode original tracking reference')
            height,width=first.shape[:2];tracker=PlanarTracker(first,plan['quad'],plan['tracking'])
            overlay=cv2.imread(str(frozen[1]),cv2.IMREAD_UNCHANGED)
            if overlay is None:raise ValueError('Overlay failed actual image decode')
            if overlay.ndim==3 and overlay.shape[2]==3:overlay=cv2.cvtColor(overlay,cv2.COLOR_BGR2BGRA)
            matte=None
            if foreground:
                if foreground['kind']=='still_image':
                    matte=cv2.imread(str(frozen[2]),cv2.IMREAD_GRAYSCALE)
                    if matte is None:raise ValueError('Foreground matte failed actual image decode')
                else:mask_capture=cv2.VideoCapture(str(frozen[2]))
            frames=private/'frames';frames.mkdir();frame=first;n=0
            while True:
                if mask_capture is not None:
                    ok,mask=mask_capture.read()
                    if not ok:raise ValueError('Actual foreground video ran out of frames')
                    matte=cv2.cvtColor(mask,cv2.COLOR_BGR2GRAY)
                corners,quality=tracker.locate(frame);metrics.append(quality)
                mixed=composite_corner_pin(frame,overlay,corners,plan['opacity'],matte)
                if not cv2.imwrite(str(frames/f'frame_{n:08d}.png'),mixed):raise RuntimeError('Cannot write actual composited frame')
                n+=1;ok,frame=capture.read()
                if not ok:break
            if n!=count:raise ValueError('Decoded tracking frame count differs from physical original')
        finally:
            capture.release()
            if mask_capture is not None:mask_capture.release()
        encoded=private/'composite.mp4';rate=f'{fps.numerator}/{fps.denominator}'
        cmd=['ffmpeg','-v','error','-nostdin','-n','-framerate',rate,'-i',str(frames/'frame_%08d.png')]
        if plan['audio']=='preserve_source':cmd+=['-i',str(frozen[0])]
        cmd+=['-map','0:v:0','-c:v','libx264','-crf','17','-pix_fmt','yuv420p','-vf','scale=in_range=full:out_range=tv:out_color_matrix=bt709,'
            'setparams=range=tv:color_primaries=bt709:color_trc=bt709:colorspace=bt709',
            '-color_primaries','bt709','-color_trc','bt709','-colorspace','bt709','-color_range','tv']
        cmd+=['-map','1:a:0','-c:a','copy'] if plan['audio']=='preserve_source' else ['-an']
        cmd+=['-movflags','+faststart',str(encoded)];subprocess.run(cmd,check=True,timeout=7200)
        # Verify actual encoded color metadata before publishing, not only requested flags.
        _actual_bt709_source(encoded)
        check=full_decode_inspection(encoded,expected={'width':width,'height':height,'duration_seconds':duration,'require_audio':plan['audio']=='preserve_source'})
        if not check['technical_delivery_verified'] or _source_timebase(encoded)!=(fps,count):raise RuntimeError('Actual planar movie failed complete picture/sound verification')
        if sha256_file(document)!=plan_hash:raise ValueError('Original planar direction changed during compositing')
        for (path,media),f in zip(originals,frozen):
            if sha256_file(path)!=media['asset_id'] or sha256_file(f)!=media['asset_id']:raise ValueError('Original or sealed VFX media changed during decode')
            vault.inspect(media['asset_id'],attestation_id=media['attestation_id'])
        output.parent.mkdir(parents=True,exist_ok=True)
        with encoded.open('rb') as stream:os.fsync(stream.fileno())
        os.link(encoded,output)
    return {'path':str(output),'sha256':sha256_file(output),'actual_tracked_frames':count,
        'source_attestations':canonical_source_attestations([
            {k:media[k] for k in ('asset_id','attestation_id')} for _,media in originals]),
        'minimum_inlier_ratio':min(x['inlier_ratio'] for x in metrics),
        'maximum_reprojection_error_pixels':max(x['reprojection_error_pixels'] for x in metrics),
        'source_sound_bitstream_preserved':plan['audio']=='preserve_source','foreground_matte_used':foreground is not None,
        'full_picture_and_sound_decode':True,'sealed_source_custody_during_decode':True,
        'tracking_scope':'planar homography; no 3D camera solve or automatic human roto','aesthetic_quality_approved':False}
