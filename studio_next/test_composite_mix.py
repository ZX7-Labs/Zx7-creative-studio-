import json
import tempfile
import unittest
import shutil
import subprocess
import wave
from pathlib import Path
from unittest.mock import patch

from studio_next.composite_mix import actual_composite_command,render_composition
from studio_next.media_vault import MediaVault


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'),
                     'Native media decoder/encoder not installed; real integration runs separately')
class LayeredProductionCompositingTests(unittest.TestCase):
    def fixture(self,root):
        workspace=Path(root)
        vault=MediaVault(workspace/"vault")
        layers=[]
        for index in range(3):
            video=workspace/f"camera_{index}.mp4"
            subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",
                "-f","lavfi","-i",f"color=c=0x{index+1}{index+2}3366:s=320x240:r=24:d=1.5",
                "-c:v","mpeg4","-q:v","5",str(video)],check=True,timeout=40)
            ref=vault.ingest(video,mime="video/mp4",rights="owner_supplied",
                source_type="owner_upload",source_id=f"owner-{index}",
                evidence="Original owner source fixture",
                owner_or_generator="owner")
            layers.append({"id":f"layer_{index}","source":video.name,
                "asset_id":ref["asset_id"],"attestation_id":ref["attestation_id"],
                "start":index*0.125,"source_in":0,"duration":1,
                "x":index*70,"y":-index*20,"width":200,"height":140,
                "opacity":1-index*.25})
        sound=workspace/"narration.wav"
        with wave.open(str(sound),"wb") as wav:
            wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(16000)
            wav.writeframes(bytes(2*16000*2))
        sound_ref=vault.ingest(sound,mime="audio/wav",rights="owner_supplied",
            source_type="owner_upload",source_id="owner_audio",
            evidence="Owner supplied this real voice track",owner_or_generator="owner")
        edit={"canvas":{"width":1080,"height":1920,"fps":24,
               "duration":2,"background":"#142A34"},
              "video_layers":layers,
              "audio_tracks":[{"id":"voice","source":sound.name,
                   "asset_id":sound_ref["asset_id"],
                   "attestation_id":sound_ref["attestation_id"],
                   "start":0.45,"source_in":0,"duration":1.0,"gain_db":-6.1}]}
        file=workspace/"composite.json"
        file.write_text(json.dumps(edit))
        return edit,file,vault

    def test_creative_engine_chooses_layers_style_camera_and_audio(self):
        with tempfile.TemporaryDirectory() as root:
            plan,_,vault=self.fixture(root)
            cmd=actual_composite_command(plan,root,vault,Path(root)/"film.mp4")
            graph=cmd[cmd.index("-filter_complex")+1]
            self.assertIn("overlay=x=140:y=-40",graph)
            self.assertIn("colorchannelmixer=aa=0.5",graph)
            self.assertIn("volume=-6.1dB",graph)
            self.assertIn("adelay=21600S:all=1",graph)
            self.assertEqual(cmd[0],"ffmpeg")

    def test_decimal_half_sample_offsets_and_trims_do_not_round_wrong_way(self):
        # 13.5 and 52.5 samples have exact, deterministic ties-to-even
        # answers (14 and 52). Binary64 multiplication can drift by one.
        with tempfile.TemporaryDirectory() as root:
            plan,_,vault=self.fixture(root)
            source=Path(root)/"48k-boundary.wav"
            with wave.open(str(source),"wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(48000)
                wav.writeframes(bytes(4800*2))
            record=vault.ingest(
                source,mime="audio/wav",rights="owner_supplied",
                source_type="owner_upload",source_id="half-sample-test",
                evidence="Synthetic silence for exact source-clock contract",
                owner_or_generator="synthetic-test-generator")
            track=plan["audio_tracks"][0]
            track.update(source=source.name,asset_id=record["asset_id"],
                         attestation_id=record["attestation_id"],
                         start=0.00028125,source_in=0.00109375,duration=0.05)
            graph=actual_composite_command(
                plan,root,vault,Path(root)/"boundary.mp4")
            filters=graph[graph.index("-filter_complex")+1]
            self.assertIn("atrim=start_sample=52:end_sample=2452",filters)
            self.assertIn("adelay=14S:all=1",filters)

    def test_one_unverified_clip_or_changed_byte_blocks_edit(self):
        with tempfile.TemporaryDirectory() as root:
            plan,_,vault=self.fixture(root)
            f=Path(root)/"camera_1.mp4"
            f.write_bytes(b"corrupted")
            with self.assertRaisesRegex(ValueError,"Source bytes differ"):
                actual_composite_command(plan,root,vault,Path(root)/"render.mp4")

    def test_director_decides_34_visual_layers_not_template_limit(self):
        with tempfile.TemporaryDirectory() as root:
            plan,_,vault=self.fixture(root)
            plan["video_layers"]=[dict(plan["video_layers"][index%3],
                                  id=f"actual_artist_layer_{index}") for index in range(34)]
            command=actual_composite_command(plan,root,vault,Path(root)/"cinema.mp4")
            self.assertIn("overlay=",command[command.index("-filter_complex")+1])
            self.assertEqual(command[command.index("-filter_complex")+1].count("]overlay="),34)

    def test_stereo_artist_balance_is_measured_in_actual_decoded_samples(self):
        import array
        import math
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            plan,document,vault=self.fixture(root)
            tone=root/"owner-actual-tone.wav"
            subprocess.run(["ffmpeg","-hide_banner","-loglevel","error",
                "-nostdin","-y","-f","lavfi","-i",
                "sine=frequency=440:sample_rate=48000:duration=1",
                "-c:a","pcm_s16le",str(tone)],check=True,timeout=45)
            proof=vault.ingest(tone,mime="audio/wav",
                rights="owner_supplied",source_type="owner_upload",
                source_id="original-440Hz-mono",
                evidence="Native rendered source audio physical waveform",
                owner_or_generator="source-owner")
            plan["canvas"].update(width=128,height=96,fps=12,duration=1)
            plan["video_layers"]=[]
            audio=plan["audio_tracks"][0]
            audio.update(source=tone.name,asset_id=proof["asset_id"],
                attestation_id=proof["attestation_id"],source_in=0,start=0,
                duration=1,gain_db=0,stereo_balance=-1)
            cmd=actual_composite_command(plan,root,vault,root/"spatial.mp4")
            self.assertIn("pan=stereo|c0=1*c0|c1=0*c1",
                          cmd[cmd.index("-filter_complex")+1])
            document.write_text(json.dumps(plan))
            movie=root/"real-stereo-audio-movie.mp4"
            result=render_composition(document,root,root/"vault",movie)
            self.assertTrue(result["full_picture_and_sound_decoder_completed"])
            raw=subprocess.check_output(["ffmpeg","-hide_banner",
                "-loglevel","error","-nostdin","-i",str(movie),
                "-map","0:a:0","-ac","2","-ar","48000",
                "-f","f32le","-"],timeout=45)
            values=array.array("f")
            values.frombytes(raw)
            left=list(values[0::2])
            right=list(values[1::2])
            self.assertGreater(len(left),1000)
            rms_left=math.sqrt(sum(x*x for x in left)/len(left))
            rms_right=math.sqrt(sum(x*x for x in right)/len(right))
            self.assertGreater(rms_left,.015)
            self.assertLess(rms_right,rms_left*.08)
            for untrusted in (float("nan"),float("inf"),True,-1.1,1.1):
                audio["stereo_balance"]=untrusted
                with self.assertRaisesRegex(ValueError,"stereo balance"):
                    actual_composite_command(plan,root,vault,root/"never.mp4")

    def test_physically_encoded_multilayer_movie_has_audio_and_rights(self):
        from studio_next.delivery_audit import _probe_details
        with tempfile.TemporaryDirectory() as root:
            plan,file,vault=self.fixture(root)
            # Deliberate modest actual media dimensions; no creative size preset.
            plan["canvas"].update(width=640,height=360,fps=24,duration=2)
            file.write_text(json.dumps(plan))
            destination=Path(root)/"physical-director-cut.mp4"
            result=render_composition(file,root,Path(root)/"vault",destination)
            proof=_probe_details(destination)
            self.assertTrue(result["verified_physically"])
            self.assertEqual((proof["width"],proof["height"]),(640,360))
            self.assertTrue(proof["audio_stream_present"])
            self.assertEqual(result["video_layers"],3)

    def test_original_keyframed_motion_and_alpha_are_derived_from_artist_frames(self):
        from studio_next.delivery_audit import _probe_details
        with tempfile.TemporaryDirectory() as root:
            film,source,vault=self.fixture(root)
            film["canvas"].update(width=640,height=360,fps=24,duration=2)
            graphic=film["video_layers"][1]
            # Isolate one moving artist-controlled layer so actual pixels
            # prove the object moved rather than merely encoding a filter.
            film["video_layers"]=[graphic]
            graphic["motion"]=[
                {"at_seconds":0,"x":12,"y":14},
                {"at_seconds":0.4,"x":90,"y":30},
                {"at_seconds":0.8,"x":180,"y":65}]
            graphic["fade_in_seconds"]=0.05
            graphic["fade_out_seconds"]=0.15
            command=actual_composite_command(film,root,vault,Path(root)/"keyframe-movie.mp4")
            graph=command[command.index("-filter_complex")+1]
            self.assertIn("if(lt(t,",graph)
            self.assertIn("fade=t=in",graph)
            self.assertIn("fade=t=out",graph)
            source.write_text(json.dumps(film))
            real=Path(root)/"keyframed-cinema.mp4"
            result=render_composition(source,root,Path(root)/"vault",real)
            meta=_probe_details(real)
            self.assertTrue(result["verified_physically"])
            self.assertEqual((meta["width"],meta["height"]),(640,360))
            self.assertTrue(meta["audio_stream_present"])
            def frame_pixel(t):
                pixels=subprocess.check_output([
                    "ffmpeg","-hide_banner","-loglevel","error",
                    "-ss",str(t),"-i",str(real),
                    "-frames:v","1","-f","rawvideo","-pix_fmt","rgb24","-"],
                    timeout=40)
                point=(40*640+40)*3
                return tuple(pixels[point:point+3])
            entering=frame_pixel(0.2)
            moved=frame_pixel(0.92)
            self.assertGreater(sum(abs(a-b) for a,b in zip(entering,moved)),20,
                "Keyframed scene did not visibly move in physically decoded movie frames")

    def test_invalid_keyframes_and_fake_model_effects_cannot_execute(self):
        with tempfile.TemporaryDirectory() as root:
            original,_,vault=self.fixture(root)
            layer=original["video_layers"][0]
            layer["motion"]=[{"at_seconds":0.8,"x":0,"y":0},
                             {"at_seconds":0.6,"x":100,"y":5}]
            with self.assertRaisesRegex(ValueError,"increasing"):
                actual_composite_command(original,root,vault,Path(root)/"invalid.mp4")
            layer["motion"]=[{"at_seconds":0,"x":0,"y":0}]
            layer["model_python"]="invent an actor with untrusted shell"
            with self.assertRaisesRegex(ValueError,"untrusted"):
                actual_composite_command(original,root,vault,Path(root)/"invalid.mp4")

    def test_exact_attested_original_still_can_animate_over_sound_without_video_forgery(self):
        from studio_next.media_vault import sha256_file
        try:
            from PIL import Image,ImageDraw
        except ImportError:
            self.skipTest("Actual decoded image pixels required")
        with tempfile.TemporaryDirectory() as root:
            plan,document,vault=self.fixture(root)
            plan["canvas"].update(width=320,height=240,duration=2)
            png=Path(root)/"owned-design.png"
            canvas=Image.new("RGB",(128,96),(15,22,44))
            painter=ImageDraw.Draw(canvas)
            painter.polygon([(18,75),(64,12),(110,75)],fill=(245,199,70))
            canvas.save(png)
            proof=vault.ingest(png,mime="image/png",rights="owner_supplied",
                source_type="owner_upload",source_id="actual-artist-still",
                evidence="Actual original decoded graphical artwork",owner_or_generator="owner")
            layer=dict(plan["video_layers"][0],
                  source=png.name,asset_id=proof["asset_id"],
                  attestation_id=proof["attestation_id"],
                  source_kind="still_image",source_in=0,duration=1.5,
                  motion=[{"at_seconds":0,"x":0,"y":20},
                          {"at_seconds":1,"x":60,"y":30}])
            plan["video_layers"]=[layer]
            command=actual_composite_command(plan,root,vault,Path(root)/"proof.mp4")
            self.assertIn("-loop",command)
            self.assertIn("-framerate",command)
            with self.assertRaisesRegex(ValueError,"source-time trim"):
                actual_composite_command(
                    {**plan,"video_layers":[{**layer,"source_in":.2}]},
                    root,vault,Path(root)/"never.mp4")
            with self.assertRaisesRegex(ValueError,"decoded, rights-attested image"):
                actual_composite_command(
                    {**plan,"video_layers":[{**layer,"source":"narration.wav",
                      "asset_id":plan["audio_tracks"][0]["asset_id"],
                      "attestation_id":plan["audio_tracks"][0]["attestation_id"]}]},
                    root,vault,Path(root)/"never.mp4")
            document.write_text(json.dumps(plan))
            result=render_composition(document,root,Path(root)/"vault",
                                      Path(root)/"real-still-editor.mp4")
            self.assertTrue(result["verified_physically"])
            self.assertTrue(result["full_picture_and_sound_decoder_completed"])
            self.assertEqual(sha256_file(png),proof["asset_id"])
            raw=subprocess.check_output(["ffmpeg","-hide_banner","-loglevel","error",
                "-ss","0.8","-i",str(Path(root)/"real-still-editor.mp4"),
                "-frames:v","1","-f","rawvideo","-pix_fmt","rgb24","-"],timeout=30)
            self.assertGreater(max(raw),60)
            self.assertTrue((Path(root)/"real-still-editor.mp4").is_file())

    def test_real_trimmed_motion_roto_matte_follows_original_picture_clock(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Requires a real still-image pixel decoder")
        from studio_next.media_vault import sha256_file
        with tempfile.TemporaryDirectory() as home:
            root=Path(home)
            plan,document,vault=self.fixture(root)
            front=root/"licensed-flat-color.png"
            Image.new("RGBA",(64,64),(250,9,9,255)).save(front)
            mask_video=root/"original-temporal-mask.mp4"
            movie=subprocess.run(["ffmpeg","-hide_banner","-loglevel","error",
                "-nostdin","-y","-f","lavfi","-i",
                "color=c=black:s=64x64:r=12:d=1",
                "-vf","drawbox=x=0:y=0:w=32:h=64:color=white:t=fill:"
                      "enable='lt(t,0.5)',"
                      "drawbox=x=32:y=0:w=32:h=64:color=white:t=fill:"
                      "enable='gte(t,0.5)'",
                "-c:v","libx264","-pix_fmt","yuv420p",str(mask_video)],
                capture_output=True,text=True,timeout=60)
            self.assertEqual(movie.returncode,0,movie.stderr)
            picture=vault.ingest(front,mime="image/png",rights="owner_supplied",
                source_type="owner_upload",source_id="original-owned-graphic",
                evidence="Source creator provided actual decoded red RGBA art",
                owner_or_generator="creator")
            mask=vault.ingest(mask_video,mime="video/mp4",
                rights="owner_supplied",source_type="owner_upload",
                source_id="timevarying-director-rotoscope",
                evidence="Original editor painted two distinct matte poses in real frames",
                owner_or_generator="creator")
            plan["canvas"]={"width":64,"height":64,"fps":12,
                            "duration":.5,"background":"#0000FF"}
            plan["video_layers"]=[{
                "id":"independent-temporal-luma-roto",
                "source":front.name,"asset_id":picture["asset_id"],
                "attestation_id":picture["attestation_id"],
                "source_kind":"still_image","start":0,"source_in":0,
                "duration":.5,"x":0,"y":0,"width":64,"height":64,
                "opacity":1,
                "matte":{"source":mask_video.name,"asset_id":mask["asset_id"],
                         "attestation_id":mask["attestation_id"],
                         "source_kind":"video","source_in":.25,"invert":False}}]
            plan["audio_tracks"]=[]
            before=(sha256_file(front),sha256_file(mask_video))
            document.write_text(json.dumps(plan))
            finished=root/"physical-rotoscope-frames.mp4"
            receipt=render_composition(document,root,root/"vault",finished)
            self.assertTrue(receipt["full_picture_and_sound_decoder_completed"])
            def pixel(t,x):
                data=subprocess.check_output([
                    "ffmpeg","-hide_banner","-loglevel","error","-nostdin",
                    "-ss",str(t),"-i",str(finished),
                    "-frames:v","1","-f","rawvideo","-pix_fmt","rgb24","-"],
                    timeout=40)
                i=(24*64+x)*3
                return tuple(data[i:i+3])
            early_left=pixel(.10,10)
            early_right=pixel(.10,50)
            late_left=pixel(.36,10)
            late_right=pixel(.36,50)
            self.assertGreater(early_left[0],170)
            self.assertGreater(early_right[2],170)
            self.assertGreater(late_left[2],170)
            self.assertGreater(late_right[0],170)
            self.assertEqual(before,(sha256_file(front),sha256_file(mask_video)))
            impossible=json.loads(document.read_text())
            impossible["video_layers"][0]["matte"]["source_in"]=.8
            with self.assertRaisesRegex(ValueError,"Roto matte exceeds"):
                actual_composite_command(impossible,root,vault,
                                         root/"never-accepted.mp4")

    def test_matte_decoder_uses_sealed_original_and_derivative_requires_its_grant(self):
        from PIL import Image
        from studio_next.media_vault import MediaCustodyError,sha256_file,canonical_source_attestations
        from studio_next.body_integration import run_body_project
        from studio_next import composite_mix
        with tempfile.TemporaryDirectory() as home:
            root=Path(home);vault=MediaVault(root/"vault")
            refs=[]
            for name,color in (("front",(255,0,0,255)),("matte",(255,255,255,255))):
                source=root/(name+".png");Image.new("RGBA",(32,32),color).save(source)
                grant=vault.ingest(source,mime="image/png",rights="owner_supplied",source_type="owner_upload",
                    source_id=name,evidence="Original owner image",owner_or_generator="owner")
                refs.append({"source":source.name,"asset_id":grant["asset_id"],"attestation_id":grant["attestation_id"]})
            plan={"canvas":{"width":32,"height":32,"fps":12,"duration":1,"background":"#0000FF"},
                "video_layers":[{"id":"picture",**refs[0],"source_kind":"still_image","start":0,
                    "source_in":0,"duration":1,"x":0,"y":0,"width":32,"height":32,"opacity":1,
                    "matte":{**refs[1],"source_kind":"still_image","source_in":0,"invert":False}}],"audio_tracks":[]}
            (root/"composite.json").write_text(json.dumps(plan))
            ir={"project":{"creative_intent":"Original matte compositing"},"shots":[{"id":"picture","purpose":"Real matte"}],
                "tool_graph":[{"id":"movie","tool_id":"body.composite_mix","purpose":"Actual native composite",
                    "inputs":{"plan":"composite.json","out":"movie.mp4"},"depends_on":[]},
                    {"id":"custody","tool_id":"body.asset_vault","purpose":"Retain exact matte grant",
                    "inputs":{"source_witness":{"$node_output":"movie"}},"depends_on":["movie"]}]}
            real_run=subprocess.run;mask=root/"matte.png";before=mask.read_bytes();seen=[]
            def swap_during_encode(argv,**kwargs):
                if "-filter_complex" in argv and str(argv[0]).endswith("ffmpeg"):
                    paths=[Path(argv[i+1]) for i,x in enumerate(argv[:-1]) if x=="-i" and Path(argv[i+1]).is_file()]
                    seen.extend(paths)
                    Image.new("RGBA",(32,32),(0,0,0,255)).save(mask)
                    try:return real_run(argv,**kwargs)
                    finally:mask.write_bytes(before)
                return real_run(argv,**kwargs)
            with patch.object(composite_mix.subprocess,"run",side_effect=swap_during_encode):
                done=run_body_project(ir,root)
            self.assertEqual(done["status"],"all_tool_results_verified",done)
            self.assertEqual(len(seen),2)
            self.assertTrue(all(".zx7-owned-sources-" in str(p) for p in seen),seen)
            movie=root/"movie.mp4"
            pixels=subprocess.check_output(["ffmpeg","-v","error","-i",str(movie),"-frames:v","1","-f","rawvideo","-pix_fmt","rgb24","-"],timeout=45)
            self.assertGreater(pixels[0],180);self.assertLess(pixels[2],30)
            digest=sha256_file(movie);grant=vault.inspect(digest)["rights_attestations"][0]
            self.assertEqual(grant.get("source_attestations"),canonical_source_attestations([
                {k:ref[k] for k in ("asset_id","attestation_id")} for ref in refs]))
            self.assertEqual(run_body_project(ir,root)["reused"],["movie","custody"])
            vault.withdraw_attestation(refs[1]["asset_id"],refs[1]["attestation_id"],reason="Matte grant withdrawn")
            with self.assertRaisesRegex(MediaCustodyError,"withdrawn"):
                vault.checkout(digest,grant["attestation_id"],root/"denied.mp4")
            self.assertEqual(mask.read_bytes(),before)
            self.assertEqual(sha256_file(movie),digest)

    def test_actual_owned_roto_matte_multiplies_original_transparency(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Native decoded RGBA artwork required")
        with tempfile.TemporaryDirectory() as home:
            root=Path(home)
            plan,file,vault=self.fixture(root)
            original=root/"human-authored-transparent.png"
            graphic=Image.new("RGBA",(64,64),(255,0,0,255))
            for y in range(16):
                for x in range(64):
                    graphic.putpixel((x,y),(255,0,0,0))
            graphic.save(original)
            mask_path=root/"owner-painted-matte.png"
            matte_png=Image.new("L",(64,64),0)
            for y in range(64):
                for x in range(32):
                    matte_png.putpixel((x,y),255)
            matte_png.save(mask_path)
            front=vault.ingest(original,mime="image/png",rights="owner_supplied",
                source_type="owner_upload",source_id="original-transparent-png",
                evidence="Direct source owner authored visible red artwork",
                owner_or_generator="creator")
            matte=vault.ingest(mask_path,mime="image/png",rights="owner_supplied",
                source_type="owner_upload",source_id="human-roto-original",
                evidence="Source owner painted pixel-exact original alpha mask",
                owner_or_generator="creator")
            mask={"source":mask_path.name,"asset_id":matte["asset_id"],
                  "attestation_id":matte["attestation_id"],
                  "source_kind":"still_image","source_in":0,"invert":False}
            plan["canvas"]={"width":64,"height":64,"fps":12,"duration":1,
                             "background":"#0000FF"}
            plan["video_layers"]=[{
                "id":"owner-visible-matte","source":original.name,
                "asset_id":front["asset_id"],"attestation_id":front["attestation_id"],
                "source_kind":"still_image","start":0,"source_in":0,
                "duration":1,"x":0,"y":0,"width":64,"height":64,
                "opacity":1,"matte":mask}]
            plan["audio_tracks"]=[]
            source_before=(original.read_bytes(),mask_path.read_bytes())
            cmd=actual_composite_command(plan,root,vault,root/"rights-matte.mp4")
            self.assertIn("blend=all_mode=multiply",cmd[cmd.index("-filter_complex")+1])
            file.write_text(json.dumps(plan))
            output=root/"real-original-layer-mask.mp4"
            rendered=render_composition(file,root,root/"vault",output)
            self.assertTrue(rendered["verified_physically"])
            pixels=subprocess.check_output([
                "ffmpeg","-hide_banner","-loglevel","error","-nostdin",
                "-i",str(output),"-frames:v","1","-f","rawvideo",
                "-pix_fmt","rgb24","-"],timeout=45)
            def pixel(x,y):
                i=(y*64+x)*3
                return tuple(pixels[i:i+3])
            upper_left=pixel(10,10)
            lower_left=pixel(10,25)
            lower_right=pixel(50,25)
            self.assertGreater(upper_left[2],180)  # original transparent stays transparent
            self.assertGreater(lower_left[0],180)  # painted matte keeps original red
            self.assertGreater(lower_right[2],180) # black matte reveals blue background
            self.assertEqual(source_before,(original.read_bytes(),mask_path.read_bytes()))
            self.assertFalse(list(root.glob(".zx7-owned-sources-*")))
            tampered=json.loads(file.read_text())
            tampered["video_layers"][0]["matte"]["asset_id"]="0"*64
            with self.assertRaises(Exception):
                actual_composite_command(tampered,root,vault,root/"rejected.mp4")
            not_video=json.loads(file.read_text())
            not_video["video_layers"][0]["matte"]["source_in"]=.25
            with self.assertRaisesRegex(ValueError,"no video trim clock"):
                actual_composite_command(not_video,root,vault,root/"rejected.mp4")

    def test_real_layer_source_duration_boundaries_before_render(self):
        with tempfile.TemporaryDirectory() as root:
            plan,_,vault=self.fixture(root)
            out=Path(root)/"must-not-invent-missing-source.mp4"
            plan["video_layers"][0]["source_in"]=1.3
            plan["video_layers"][0]["duration"]=0.6
            with self.assertRaisesRegex(ValueError,"source trim exceeds"):
                actual_composite_command(plan,root,vault,out)
            self.assertFalse(out.exists())
            plan["video_layers"][0]["source_in"]=0
            plan["video_layers"][0]["duration"]=1
            plan["audio_tracks"][0]["source_in"]=1.6
            plan["audio_tracks"][0]["duration"]=0.8
            with self.assertRaisesRegex(ValueError,"source trim exceeds"):
                actual_composite_command(plan,root,vault,out)
            self.assertFalse(out.exists())

    def test_concurrent_editor_cannot_overwrite_or_delete_approved_movie(self):
        from studio_next import composite_mix
        from studio_next.media_vault import sha256_file
        with tempfile.TemporaryDirectory() as workspace:
            root=Path(workspace)
            plan,source,vault=self.fixture(root)
            plan["canvas"].update(width=320,height=240,duration=2)
            source.write_text(json.dumps(plan))
            previously_approved=root/"other-editor-accepted.mp4"
            first=render_composition(source,root,root/"vault",previously_approved)
            self.assertTrue(first["full_picture_and_sound_decoder_completed"])
            master_digest=sha256_file(previously_approved)
            planned=root/"race-at-final-movie.mp4"
            original_link=composite_mix.os.link
            raced=False
            def first_editor_wins(stage,final,*args,**kwargs):
                nonlocal raced
                if Path(final)==planned:
                    self.assertIn(".zx7-composite-render-",str(stage))
                    shutil.copyfile(previously_approved,planned)
                    raced=True
                return original_link(stage,final,*args,**kwargs)
            with patch.object(composite_mix.os,"link",side_effect=first_editor_wins):
                with self.assertRaises(FileExistsError):
                    render_composition(source,root,root/"vault",planned)
            self.assertTrue(raced)
            self.assertEqual(sha256_file(planned),master_digest)
            self.assertEqual(sha256_file(previously_approved),master_digest)
            self.assertFalse(list(root.glob(".zx7-composite-render-*")))
            self.assertFalse(list(root.glob(".zx7-owned-sources-*")))

    def test_camera_movie_longer_than_its_audio_cannot_invent_missing_sound(self):
        with tempfile.TemporaryDirectory() as root:
            plan,_,vault=self.fixture(root)
            camera=Path(root)/"picture-two-seconds-audio-one-second.mp4"
            command=["ffmpeg","-hide_banner","-loglevel","error","-nostdin",
                     "-y","-f","lavfi","-i",
                     "color=c=red:s=160x90:r=24:d=2",
                     "-f","lavfi","-i",
                     "sine=frequency=540:sample_rate=48000:duration=1",
                     "-c:v","libx264","-c:a","aac",str(camera)]
            subprocess.run(command,check=True,capture_output=True,timeout=45)
            record=vault.ingest(camera,mime="video/mp4",rights="owner_supplied",
                source_type="owner_upload",source_id="original-camera-short-sound",
                evidence="Physically recorded differing picture and sound clocks",
                owner_or_generator="owner")
            audio=plan["audio_tracks"][0]
            audio.update(source=camera.name,asset_id=record["asset_id"],
                         attestation_id=record["attestation_id"],
                         start=0,source_in=1.30,duration=.40)
            out=Path(root)/"must-never-imply-missing-speech.mp4"
            with self.assertRaisesRegex(ValueError,"source trim exceeds"):
                actual_composite_command(plan,root,vault,out)
            self.assertFalse(out.exists())
            audio.update(source_in=.35,duration=.4)
            args=actual_composite_command(plan,root,vault,out)
            self.assertIn("-filter_complex",args)

    def test_mutable_checkout_swap_cannot_change_cas_sealed_camera_or_sound(self):
        from studio_next import composite_mix
        from studio_next.media_vault import sha256_file
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as root:
            plan,document,vault=self.fixture(root)
            plan["canvas"].update(width=320,height=240,fps=24,duration=2)
            document.write_text(json.dumps(plan),encoding="utf-8")
            original=Path(root)/"camera_0.mp4"
            saved=original.read_bytes()
            replacements=(Path(root)/"camera_1.mp4").read_bytes()
            hashes={layer["asset_id"] for layer in (
                plan["video_layers"]+plan["audio_tracks"])}
            actual_run=subprocess.run
            seen=[]
            def intercept(argv,**kwargs):
                if argv and argv[0]=="ffmpeg" and "-filter_complex" in argv:
                    files=[Path(argv[i+1]) for i,v in enumerate(argv[:-1])
                           if v=="-i"]
                    self.assertEqual(len(files),4)
                    for path in files:
                        self.assertIn(".zx7-owned-sources-",str(path))
                        self.assertFalse(path.stat().st_mode & 0o222)
                        self.assertIn(sha256_file(path),hashes)
                    seen.extend(files)
                    original.write_bytes(replacements)
                    try:
                        return actual_run(argv,**kwargs)
                    finally:
                        original.write_bytes(saved)
                return actual_run(argv,**kwargs)
            movie=Path(root)/"original-artist-mixed.mp4"
            with patch.object(composite_mix.subprocess,"run",side_effect=intercept):
                proof=render_composition(document,root,Path(root)/"vault",movie)
            self.assertTrue(proof["verified_physically"])
            self.assertTrue(proof["full_picture_and_sound_decoder_completed"])
            self.assertTrue(proof["sealed_original_cas_during_decode"])
            self.assertEqual(sha256_file(original),plan["video_layers"][0]["asset_id"])
            self.assertTrue(movie.is_file())
            self.assertEqual(len(seen),4)
            self.assertFalse(any(x.exists() for x in seen))
            self.assertFalse(list(Path(root).glob(".zx7-owned-sources-*")))

    def test_real_mixer_output_must_match_movie_bytes(self):
        with tempfile.TemporaryDirectory() as root:
            plan,file,vault=self.fixture(root)
            output=Path(root)/"unique.mp4"
            def fake_runner(argv,check,timeout):
                Path(argv[-1]).write_bytes(b"encoded bytes"*100)
            def fake_probe(path):
                self.assertTrue(path.is_file())
                return {"width":1080,"height":1920,
                        "duration_seconds":2.0,"audio_stream_present":True}
            result=render_composition(file,root,Path(root)/"vault",output,
                 runner=fake_runner,probe=fake_probe)
            self.assertFalse(result["verified_physically"])
            self.assertTrue(result["test_runner_or_probe_injected"])
            self.assertFalse(result["full_picture_and_sound_decoder_completed"])
            self.assertEqual(result["video_layers"],3)
            with self.assertRaises(ValueError):
                render_composition(file,root,Path(root)/"vault",output,
                 runner=fake_runner,probe=fake_probe)

if __name__=="__main__":unittest.main()
