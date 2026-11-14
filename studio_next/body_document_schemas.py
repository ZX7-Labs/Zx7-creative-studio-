"""Queryable versioned JSON authoring contracts for native media instruments.

Schemas validate document shape. Native preflight independently verifies media,
rights, exact source duration, tool availability and cross-field semantics.
No composition, voice, aesthetic, score or shot plan is supplied here.
"""
from copy import deepcopy
import hashlib
import json
import math
import re
from .blender_scene import _MATERIAL_SCALARS,_CLOTH_FLOATS,_CLOTH_CONTACT
from .body_visual_contract import visual_graph_contract


def obj(required, optional=None):
    return {"type": "object", "required": list(required),
            "properties": {**required, **(optional or {})}, "additionalProperties": False}


def array(item, **limits):
    return {"type": "array", "items": item, **limits}


def number(low=None, high=None, *, integer=False, positive=False):
    result = {"type": "integer" if integer else "number"}
    if low is not None: result["minimum"] = low
    if high is not None: result["maximum"] = high
    if positive: result["exclusiveMinimum"] = 0
    return result


def choice(*values):
    return {"enum": list(values)}


TEXT = {"type": "string", "minLength": 1}
DIGEST = {"type": "string", "pattern": r"^[0-9a-f]{64}$"}
COLOR = {"type": "string", "pattern": r"^#[0-9a-fA-F]{6}$"}
TIME = number(0)
POSITIVE = number(positive=True)
PIXEL = number(integer=True)
SIZE = number(1, integer=True)
SOURCE = obj({"source": TEXT, "asset_id": DIGEST, "attestation_id": TEXT})
RATE = obj({"numerator": SIZE, "denominator": SIZE})
SOUND = choice("preserve_source", "intentional_silence")
PAIR = array(TIME, minItems=2, maxItems=2)

_SOURCE_FIELDS = SOURCE["properties"]
_TIMING = {"start": TIME, "source_in": TIME, "duration": POSITIVE}
_VIDEO = obj({"id": TEXT, **_SOURCE_FIELDS, **_TIMING,
              "x": PIXEL, "y": PIXEL, "width": SIZE, "height": SIZE,
              "opacity": number(0, 1)}, {
    "source_kind": choice("video", "still_image"),
    "motion": array(obj({"at_seconds": TIME, "x": PIXEL, "y": PIXEL})),
    "fade_in_seconds": TIME, "fade_out_seconds": TIME,
    "chroma_key": obj({"color": COLOR, "similarity": number(high=1, positive=True), "blend": number(0, 1)}),
    "matte": obj({**_SOURCE_FIELDS, "source_kind": choice("video", "still_image"),
                  "source_in": TIME, "invert": {"type": "boolean"}})})
_AUDIO = obj({"id": TEXT, **_SOURCE_FIELDS, **_TIMING, "gain_db": number(-120, 120)}, {
    "gain_keyframes": array(obj({"at_seconds": TIME, "gain_db": number(-120, 120)})),
    "stereo_balance": number(-1, 1)})
_SEQUENCE = obj({"frame_rate": RATE, "frame_size": obj({"width": SIZE, "height": SIZE}),
    "clips": array(obj({**_SOURCE_FIELDS, "first_frame": number(0, integer=True),
                       "end_frame": SIZE, "audio": SOUND}), minItems=1, maxItems=128)})
_NATIVE_TRANSFORM = obj({"aspect":choice("preserve","distort"),
    "keyframes":array(obj({"frame":number(0,integer=True),
        "x":number(-32768,32768),"y":number(-32768,32768),
        "width":number(0,16384,positive=True),"height":number(0,16384,positive=True),
        "rotation_degrees":number(-36000,36000)}),minItems=1,maxItems=128)})
_NATIVE_TRANSFORM["description"]=(
    "Upper-layer pixel rectangle and center rotation in degrees, applied before blending. "
    "Keys begin at film frame 0, interpolate linearly and hold after the last key; "
    "preserve fits centered within the rectangle; distort fills it independently on each axis.")
_NATIVE_MASK=obj({"keyframes":array(obj({"frame":number(0,integer=True),
    "x":number(-32768,32768),"y":number(-32768,32768),
    "width":number(0,16384,positive=True),"height":number(0,16384,positive=True),
    "rounding":number(0,1)}),minItems=1,maxItems=128)})
_NATIVE_MASK["description"]=(
    "Upper-layer alpha window in original source-canvas pixels BEFORE layer geometry; "
    "outside is transparent. Linear film-frame keys begin at zero and hold after the last key. "
    "Rounding 0 is rectangular; 1 uses half the shorter side as the corner radius.")
_NATIVE_GRADE_FIELDS={name:number(0 if name.startswith("lift_") else .01,5)
    for kind in ("lift","gamma","gain") for channel in ("r","g","b")
    for name in (kind+"_"+channel,)}
_NATIVE_GRADE=obj({"keyframes":array(obj({
    "frame":number(0,integer=True),**_NATIVE_GRADE_FIELDS}),minItems=1,maxItems=128)})
_NATIVE_GRADE["description"]=(
    "Native MLT display-referred per-picture-track lift/gamma/gain on original BT.709 source. "
    "Nine independently authored RGB channels, each evaluated on the film-frame clock. "
    "All nine controls per keyframe, linear interpolation and last-key hold. "
    "This is not an ACES/scene-linear or HDR-mastering transformation.")
_NATIVE_TONE=obj({
    "order":array(choice("contrast","saturation"),minItems=2,maxItems=2),
    "keyframes":array(obj({"frame":number(0,integer=True),
        "contrast":number(0,1),"saturation":number(0,1)}),minItems=1,maxItems=128)})
_NATIVE_TONE["description"]=(
    "Director-ordered native Frei0r contrast/saturation on attested BT.709 picture. "
    "Both independently animated filters appear exactly once. The native neutral "
    "contrast 0.5 and saturation 0.125 preserve the original image. Full film clock.")

_SCHEMAS = {
    "body.visual_graph": ("plan", visual_graph_contract()),
    "body.composite_mix": ("plan", obj({
        "canvas": obj({"width": SIZE, "height": SIZE, "fps": SIZE,
                       "duration": POSITIVE, "background": COLOR}, {
            "color_semantics": obj({"input": choice("bt709"), "output": choice("bt709")}),
            "audio_bus": obj({"sample_rate": choice(48000, 96000),
                              "channel_layout": choice("stereo", "5.1")})}),
        "video_layers": array(_VIDEO), "audio_tracks": array(_AUDIO)})),
    "body.sequence_cuts": ("plan", _SEQUENCE),
    "body.mlt_owned_export": ("plan", obj({
        "frame_rate": RATE,
        "frame_size": obj({"width": SIZE, "height": SIZE}),
        "tracks": array(obj({"clips": array(obj({
            "source": TEXT, "asset_id": TEXT, "attestation_id": TEXT,
            "position_frame": number(0, integer=True),
            "first_frame": number(0, integer=True), "end_frame": SIZE,
            "audio": choice("intentional_silence")},{
            "clip_grade":_NATIVE_GRADE}), minItems=0, maxItems=128)},{
            "blend_mode":choice("normal","multiply","screen","overlay"),
            "transform":_NATIVE_TRANSFORM,
            "mask":_NATIVE_MASK,
            "grade":_NATIVE_GRADE,
            "tone":_NATIVE_TONE,
            "opacity":number(0,1),
            "opacity_keyframes":array(obj({"frame":number(0,integer=True),
                "opacity":number(0,1)}),minItems=2,maxItems=128)}),
            minItems=1, maxItems=8)},{
        "audio_tracks": array(obj({"clips":array(obj({
            "source":TEXT,"asset_id":DIGEST,"attestation_id":TEXT,
            "position_frame":number(0,integer=True),
            "first_frame":number(0,integer=True),
            "end_frame":SIZE}),minItems=1,maxItems=128)},{
                "gain_db":number(-96,24),
                "gain_keyframes":array(obj({"frame":number(0,integer=True),
                    "gain_db":number(-96,24)}),minItems=2,maxItems=128),
                "pan":number(0,1),
                "pan_keyframes":array(obj({"frame":number(0,integer=True),
                    "pan":number(0,1)}),minItems=2,maxItems=128)}),maxItems=4)})),
    "body.mlt_owned_revision": ("operation", {"oneOf":[
        obj({"operations":array({"oneOf":[
            obj({"op":choice("add","replace","test"),
                 "path":{"type":"string"},"value":{}}),
            obj({"op":choice("remove"),
                 "path":{"type":"string"}})]},minItems=1,maxItems=512)}),
        obj({"edits":array({"oneOf":[
            obj({"kind":choice("blade"),
                 "frame":number(0,integer=True),
                 "picture_tracks":array(number(0,integer=True),maxItems=8),
                 "audio_tracks":array(number(0,integer=True),maxItems=4)}),
            obj({"kind":choice("ripple_insert","ripple_delete"),
                 "frame":number(0,integer=True),"frames":SIZE,
                 "picture_tracks":array(number(0,integer=True),maxItems=8),
                 "audio_tracks":array(number(0,integer=True),maxItems=4),
                 "automation":choice("preserve_source_frame_values")}),
            obj({"kind":choice("roll","slip","slide"),
                 "delta_frames":number(-1000000,1000000,integer=True),
                 "picture_targets":array(obj({"track":number(0,integer=True),
                    "clip":number(0,integer=True)}),maxItems=8),
                 "audio_targets":array(obj({"track":number(0,integer=True),
                    "clip":number(0,integer=True)}),maxItems=4),
                 "automation":choice("lock_to_timeline")}),
            obj({"kind":choice("place"),
                 "effects":choice("inherit_destination_track_at_film_time"),
                 "placements":array(obj({
                     "domain":choice("picture","sound"),
                     "from_track":number(0,integer=True),
                     "clip":number(0,integer=True),
                     "to_track":number(0,integer=True),
                     "at_frame":number(0,1000000,integer=True)}),
                     minItems=1,maxItems=256)})
            ]},minItems=1,maxItems=128)})
        ]}),
    "body.timeline_revision": ("plan", _SEQUENCE),
    "body.otio_owned_export": ("plan", _SEQUENCE),
    "body.retime": ("plan", obj({**_SOURCE_FIELDS, "source_fps": RATE,
        "segments": array(obj({"first_frame": number(0, integer=True), "end_frame": SIZE,
                               "speed": RATE}), minItems=1, maxItems=4096), "audio": SOUND}, {
        "interpolation": choice("frame_repeat", "motion_compensated")})),
    "body.review": ("plan", obj({"media": SOURCE,
        "timecodes_seconds": array(TIME, minItems=1, maxItems=24),
        "audio_windows_seconds": array(PAIR, maxItems=24)})),
    "body.loudness": ("plan", obj({"media": SOURCE})),
    "body.color_lut": ("plan", obj({"media": SOURCE,
        "color_transform": obj({"kind": choice("display_referred_3d_lut"),
            "input_color_space": choice("bt709"), "output_color_space": choice("bt709"),
            "cube": SOURCE, "interpolation": choice("tetrahedral", "trilinear")}),
        "output_profile": choice("h264_8bit_sdr", "prores_10bit_sdr")})),
    "body.film_finish": ("plan", obj({"media": SOURCE, "ops": obj({
        "video_ops": array({"oneOf": [
            obj({"kind": choice("color_eq"), "brightness": number(-1,1),
                 "contrast": number(0,3), "saturation": number(0,5), "gamma": number(.1,10)}),
            obj({"kind": choice("denoise"), "luma_spatial": number(0,20), "luma_temporal": number(0,20)}),
            obj({"kind": choice("sharpen"), "strength": number(-2,5)})]}),
        "audio_ops": array({"oneOf": [obj({"kind": choice("gain"), "db": number(-60,30)}),
            obj({"kind": choice("loudnorm"), "integrated_lufs": number(-70,-5),
                 "true_peak_dbfs": number(-9,0), "loudness_range": number(1,30)})]})})})),
}

# The 2D instrument's drawing grammar is technical geometry, not a supplied
# composition. All positions, words, durations, motion and sounds are authored.
_RGBA={"type":"string","pattern":r"^#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?$"}
_XY=array(number(),minItems=2,maxItems=2)
_BOX=array(number(),minItems=4,maxItems=4)
_EMPTY_TEXT={"type":"string"}
_PAINT={"fill":_RGBA,"stroke":_RGBA,"width":number(.1,64)}
_DRAWINGS=[]
for _kind,_fields,_optional in (
    ("rect",{"box":_BOX},{"radius":number(0,1024)}),
    ("ellipse",{"box":_BOX},{}),
    ("line",{"points":array(_XY,minItems=2,maxItems=200)},{}),
    ("polygon",{"points":array(_XY,minItems=3,maxItems=200)},{}),
    ("text",{"text":TEXT,"at":_XY,"size":number(2,256)},
        {"font":TEXT,"align":choice("left","center","right"),"leading":number(.5,3)})):
    _DRAWINGS.append(obj({"type":choice(_kind),**_fields},{**_PAINT,**_optional}))
_KEYFRAME={"type":"array","prefixItems":[TIME,number(),choice("linear","smooth","in","out","spring")],
           "minItems":2,"maxItems":3}
_PROPS={name:number() for name in ("x","y","scale","scale_x","scale_y","angle","opacity","reveal","blur")}
_LAYER=obj({"asset":TEXT},{**_PROPS,"in":TIME,"out":TIME,
    "shadow":obj({}, {"alpha":number(0,1),"blur":TIME,"dx":number(),"dy":number()}),
    "animate":obj({}, {key:{"oneOf":[number(),array(_KEYFRAME,minItems=1)]} for key in _PROPS})})
_VOICE={"type":"string","pattern":r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$"}
_VOICE_SETTINGS=obj({}, {"speed":number(.1,4),"silence_duration":number(0,10),
    "total_steps":number(1,100,integer=True),"max_chunk_length":number(1,10000,integer=True),"lang":TEXT})
_SYNTH=obj({"type":choice("synth"),"at":TIME,"seconds":POSITIVE,"gain":number(0,16),
    "partials":array(obj({"start_hz":number(0,24000),"end_hz":number(0,24000),
        "amplitude":number(0,16),"phase_radians":number(-1e6,1e6)}),maxItems=64),
    "noise_gain":number(0,1),"seed":number(0,integer=True),
    "envelope":array(_XY,minItems=2,maxItems=128)})
_CUE={"oneOf":[_SYNTH,obj({"type":choice("ink","paper","tap"),"at":TIME},
    {"seconds":POSITIVE,"gain":number(0,1),"hz":number(30,12000)})]}
_NOTE=obj({"at":TIME,"midi":number(0,127)},
          {"seconds":POSITIVE,"gain":number(0,10),"decay":number(0,10)})
_MIX=obj({}, {"voice_gain_db":number(-120,120),"fade_in_seconds":TIME,"fade_out_seconds":TIME,
    "peak_ceiling":{"oneOf":[number(high=1,positive=True),{"type":"null"}]},
    "loudness":{"oneOf":[obj({"integrated_lufs":number(-70,-5),"true_peak_dbfs":number(-9,0),
                              "loudness_range":number(1,30)}),{"type":"null"}]}})
_MOTION=obj({
    "project":obj({"title":TEXT,"creative_intent":TEXT,"width":number(320,2160,integer=True),
        "height":number(320,4096,integer=True),"background":_RGBA,"voice":_VOICE},
        {"voice_settings":_VOICE_SETTINGS,"score":array(_NOTE),"audio_mix":_MIX,
         "background_noise":{"oneOf":[obj({"gain":number(0,255),"seed":number(0,integer=True)}),{"type":"null"}]}}),
    "assets":array(obj({"id":TEXT,"status":choice("verified"),
        "rights":choice("generated_original","appropriately_licensed"),"location":TEXT,
        "artwork":obj({"size":_XY,"items":array({"oneOf":_DRAWINGS},minItems=1,maxItems=300)})}),minItems=1),
    "shots":array(obj({"id":TEXT,"purpose":TEXT,"duration_seconds":number(.5,60),
        "narration":_EMPTY_TEXT,"asset_refs":array(TEXT),"layers":array(_LAYER,minItems=1,maxItems=100)},
        {"fact_refs":array(TEXT),"voice":_VOICE,"voice_settings":_VOICE_SETTINGS,"cues":array(_CUE)}),minItems=1),
    "tool_graph":array(obj({"id":TEXT,"tool_id":choice("motion_studio.composite"),
        "purpose":TEXT,"inputs":obj({}),"depends_on":array(TEXT,maxItems=0)}),minItems=1,maxItems=1)},
    {"owner_facts":{"type":"object","required":[],"properties":{},"additionalProperties":True}})
_SCHEMAS["body.motion2d"]=("original_film_ir",_MOTION)
_SCHEMAS["body.render_edit_owned"]=("edit",obj({
    "format":obj({"width":SIZE,"height":SIZE,"fps":SIZE,"framing":choice("fit","fill"),"background":COLOR}),
    "clips":array(obj({"id":TEXT,**_SOURCE_FIELDS,"audio":SOUND,
        "rights":choice("owner_supplied","generated_original","appropriately_licensed")}),minItems=1,maxItems=128)}))
_SCHEMAS["body.temporal_evidence"]=("plan",obj({"media":SOURCE,
    "preview":obj({"width":number(8,160,integer=True),"height":number(8,160,integer=True)})}))
_SCHEMAS["body.generate_video"]=("video_job",obj({"model_id":TEXT,"prompt":TEXT,"negative_prompt":_EMPTY_TEXT,
    "width":number(1,65536,integer=True),"height":number(1,65536,integer=True),
    "frames":number(1,65536,integer=True),"fps":number(1,65536,integer=True),
    "seed":number(0,2**64-1,integer=True)},
    {"images":array(obj({"binding":TEXT,"media":SOURCE}),maxItems=16)}))

_VEC3=array(number(-1e7,1e7),minItems=3,maxItems=3)
_RGB=array(number(0,1),minItems=3,maxItems=3)
_VEC4=array(number(0,1),minItems=4,maxItems=4)
_CURVE=array(obj({"frame":SIZE,"value":_VEC3}),minItems=1)
_TRANSFORM={"location":_VEC3,"rotation_degrees":_VEC3,
            "scale":array(number(.0001,100000),minItems=3,maxItems=3)}
_ANIMATION={"animate":obj({}, {key:_CURVE for key in _TRANSFORM})}
_MODIFIER={"oneOf":[obj({"kind":choice("bevel"),"width":number(.000001,1000),"segments":number(1,12,integer=True),"angle_degrees":number(0,180)}),
    obj({"kind":choice("solidify"),"thickness":number(.000001,1000),"offset":number(-1,1)}),
    obj({"kind":choice("subdivision"),"levels":number(0,4,integer=True)})]}
_ANIMATION.update({"parent":TEXT,"interpolation":choice("LINEAR","BEZIER","CONSTANT"),"modifiers":array(_MODIFIER,maxItems=8)})
_UV=array(number(-10000,10000),minItems=2,maxItems=2)
_PBR_OPTIONS={"transmission":number(0,1),"ior":number(1,4),"coat":number(0,1),"coat_roughness":number(0,1),
    "sheen":number(0,1),"emission_color":_RGB,"emission_strength":number(0,100000),"normal_strength":number(0,10),
    "texture_alpha":{"type":"boolean"},**{key:TEXT for key in ("base_color_texture","roughness_texture","metallic_texture","normal_texture","emission_texture")}}
_RIGID=obj({"type":choice("ACTIVE","PASSIVE"),
    "collision_shape":choice("BOX","SPHERE","CAPSULE","CYLINDER","CONE","CONVEX_HULL","MESH"),
    "mass":number(.001,1e7),"friction":number(0,10),"restitution":number(0,1),
    "linear_damping":number(0,1),"angular_damping":number(0,1),"collision_margin":number(0,1),
    "kinematic":{"type":"boolean"}})
_ANIMATION["rigid_body"]=_RIGID
_CLOTH=obj({**{key:number(lo,hi) for key,(lo,hi) in _CLOTH_FLOATS.items()},
    "quality":number(1,80,integer=True),"pins":array(obj({"vertex":number(0,integer=True),"weight":number(0,1)})),
    "collisions":{"type":"boolean"},"collision_distance":number(.001,1),"collision_quality":number(1,80,integer=True),
    "self_collision":{"type":"boolean"},"self_distance":number(.001,.1),"self_friction":number(0,80)})
_SHAPE_KEYS=array(obj({"id":TEXT,"vertices":array(_VEC3,minItems=3),"value":number(0,1)},
    {"animate":array(obj({"frame":SIZE,"value":array(number(0,1),minItems=1,maxItems=1)}),minItems=1),
     "interpolation":choice("LINEAR","BEZIER","CONSTANT")}),minItems=1)
_ANIMATION.update({"cloth_collision":obj({key:number(lo,hi) for key,(lo,hi) in _CLOTH_CONTACT.items()}),
    "liquid_domain":obj({"resolution":number(6,512,integer=True),"mesh_scale":number(1,4,integer=True),
        "particle_radius":number(.01,10),"time_scale":number(.0001,10),"flip_ratio":number(0,1),"viscosity":number(0,10)}),
    "liquid_flow":obj({"behavior":choice("GEOMETRY","INFLOW","OUTFLOW"),"surface_distance":number(0,10),
        "velocity":array(number(-1000,1000),minItems=3,maxItems=3)}),
    "liquid_obstacle":obj({"surface_distance":number(0,10),"planar":{"type":"boolean"}})})
_ANIMATION['liquid_domain']['description']='Native liquid mesh baking requires Blender 4.5+. This adapter does not provide variable-topology velocity-aware motion blur or EXR vector passes.'
_PBR_OPTIONS.update({"anisotropic":number(0,1),"anisotropic_rotation":number(0,1),
    "subsurface":number(0,1),"subsurface_scale":number(.000001,1000),
    "subsurface_radius":array(number(0,1000),minItems=3,maxItems=3),
    "coat_ior":number(1,4),"sheen_roughness":number(0,1),
    "surface_noise":obj({"scale":number(.000001,1e6),"detail":number(0,15),"roughness":number(0,1),
        "distortion":number(-1000,1000),"mapping_scale":array(number(.000001,1e6),minItems=3,maxItems=3)},
        {"bump":obj({"strength":number(0,1),"distance":number(0,1000)}),
         "roughness_range":array(number(.001,1),minItems=2,maxItems=2),
         "color_range":array(_VEC4,minItems=2,maxItems=2)}),
    "volume":obj({}, {"absorption":obj({"color":_RGB,"density":number(0,1000)}),
                      "scatter":obj({"color":_RGB,"density":number(0,1000),"anisotropy":number(-.99,.99)})})})
_PBR_OPTIONS.update({"interpolation":choice("LINEAR","BEZIER","CONSTANT"),"animate":obj({}, {
    **{key:array(obj({"frame":SIZE,"value":array(number(low,high),minItems=1,maxItems=1)}),minItems=1)
       for key,(low,high) in _MATERIAL_SCALARS.items()},
    "color":array(obj({"frame":SIZE,"value":_VEC4}),minItems=1),
    "emission_color":array(obj({"frame":SIZE,"value":_RGB}),minItems=1)})})
_RENDER_SETTINGS=obj({}, {"seed":number(0,2**31-1,integer=True),"adaptive_threshold":number(0,1),
    "motion_blur":obj({"shutter":number(.000001,2),"position":choice("START","CENTER","END")}),
    "view_transform":choice("AgX","Standard","Filmic","Raw"),"exposure":number(-32,32),
    **{key:number(0,1024,integer=True) for key in ("max_bounces","diffuse_bounces","glossy_bounces",
         "transmission_bounces","volume_bounces","transparent_max_bounces")}})
_OBJECT_BASE={"id":TEXT,"material":TEXT,**_TRANSFORM}
_BLENDER=obj({"shot_id":TEXT,"width":SIZE,"height":SIZE,"fps":SIZE,"frames":SIZE,
    "world":obj({"color":_RGB,"strength":number(0,100)},
        {"environment_texture":TEXT,"environment_rotation_degrees":number(-36000,36000)}),
    "camera":obj({"location":_VEC3,"target":_VEC3,"lens_mm":number(1,300)},
        {"animate_location":_CURVE,"animate_target":_CURVE,
         "depth_of_field":obj({"focus_distance":number(.001,10000),"fstop":number(.1,100)},
             {"focus_object":TEXT,"aperture_blades":{"oneOf":[choice(0),number(3,16,integer=True)]},
              "aperture_ratio":number(.01,100),"aperture_rotation_degrees":number(-36000,36000)}),
         "interpolation":choice("LINEAR","BEZIER","CONSTANT"),"sensor_width_mm":number(1,1000),
         "shift_x":number(-10,10),"shift_y":number(-10,10),
         "animate_lens_mm":array(obj({"frame":SIZE,"value":array(number(1,300),minItems=1,maxItems=1)}),minItems=1),
         "animate_focus_distance":array(obj({"frame":SIZE,"value":array(number(.001,10000),minItems=1,maxItems=1)}),minItems=1)}),
    "materials":array(obj({"id":TEXT,"color":_VEC4,"metallic":number(0,1),"roughness":number(.001,1)},_PBR_OPTIONS),minItems=1),
    "objects":array({"oneOf":[
        obj({**_OBJECT_BASE,"type":choice("cube","uv_sphere","ico_sphere","cylinder","cone","torus","plane","empty")},_ANIMATION),
        obj({**_OBJECT_BASE,"type":choice("custom_mesh"),"vertices":array(_VEC3,minItems=3),
             "faces":array(array(number(0,integer=True),minItems=3),minItems=1)},
            {**_ANIMATION,"uvs":array(array(_UV,minItems=3),minItems=1),"cloth":_CLOTH,"shape_keys":_SHAPE_KEYS}),
        obj({**_OBJECT_BASE,"type":choice("lathe"),"profile":array(array(number(-1e7,1e7),minItems=2,maxItems=2),minItems=2,maxItems=512),
            "segments":number(8,512,integer=True),"caps":{"type":"boolean"}},_ANIMATION),
        obj({**_OBJECT_BASE,"type":choice("licensed_glb"),"asset":TEXT,
             "rights":choice("owner_supplied","appropriately_licensed")},_ANIMATION)]},minItems=1),
    "lights":array(obj({"id":TEXT,"type":choice("AREA","POINT","SUN","SPOT"),
        "location":_VEC3,"rotation_degrees":_VEC3,"energy":number(0,1e7),"color":_RGB},
        {"size":number(.01,10000),"size_y":number(.01,10000),"shape":choice("DISK","SQUARE","RECTANGLE","ELLIPSE"),
         "interpolation":choice("LINEAR","BEZIER","CONSTANT"),"animate":obj({}, {key:_CURVE for key in ("location","rotation_degrees")}),
         "animate_energy":array(obj({"frame":SIZE,"value":array(number(0,1e7),minItems=1,maxItems=1)}),minItems=1),
         "animate_color":array(obj({"frame":SIZE,"value":_RGB}),minItems=1)}),minItems=1)},
    {"samples":SIZE,"denoise":{"type":"boolean"},"render_settings":_RENDER_SETTINGS,
     "physics":obj({"gravity":array(number(-10000,10000),minItems=3,maxItems=3)}, {
         "substeps_per_frame":number(1,1000,integer=True),"solver_iterations":number(1,1000,integer=True)})})
for _tool in ("body.blender3d","body.exr_passes","body.exr_checkpoint"):
    _SCHEMAS[_tool]=("scene_json",_BLENDER)
_SCHEMAS["body.cgi_shot"]=("plan",obj({"scene":_BLENDER,
    "assets":array(obj({"name":TEXT,"media":SOURCE}))}))
_SCHEMAS["body.planar_insert"]=("plan",obj({"media":SOURCE,"overlay":SOURCE,
    "quad":array(_UV,minItems=4,maxItems=4),"opacity":number(0,1),
    "audio":choice("preserve_source","intentional_silence"),
    "tracking":obj({"max_features":number(32,20000,integer=True),"min_matches":number(8,2000,integer=True),
        "min_inlier_ratio":number(.1,1),"ransac_pixels":number(.1,30),"max_reprojection_error":number(.1,30)})},
    {"foreground":obj({"media":SOURCE,"kind":choice("still_image","video")})}))
_ACES={"source":SOURCE,"source_color_space":choice("Linear Rec.709 (sRGB)"),
    "alpha_association":choice("associated_scene_linear"),"scene_linear_background_rgb":_RGB,
    "display":choice("sRGB - Display"),"view":choice("ACES 2.0 - SDR 100 nits (Rec.709)")}
_SCHEMAS["body.aces2_movie"]=("plan",obj(_ACES))
_SCHEMAS["body.aces2_preview"]=("plan",obj({**_ACES,"frame_index":SIZE}))
_INDEX=number(0,integer=True)
_DELTA=number(-2000000,2000000,integer=True)
_EDITOR_OPS=[]
for _kind,_fields in (
    ("roll",{"at":_INDEX,"delta":_DELTA}),
    ("slip",{"clip":_INDEX,"delta":_DELTA}),
    ("slide",{"clip":_INDEX,"delta":_DELTA}),
    ("ripple_trim",{"clip":_INDEX,"edge":choice("in","out"),"delta":_DELTA}),
    ("split",{"clip":_INDEX,"offset":SIZE}),
    ("reorder",{"clip":_INDEX,"to":_INDEX})):
    _EDITOR_OPS.append(obj({"kind":choice(_kind),**_fields}))
_SECONDARY={"body.timeline_revision":{"operation":obj({
    "operations":array({"oneOf":_EDITOR_OPS},minItems=1,maxItems=64)})}}
from .body_motion_project import motion_document_schema
_SCHEMAS["body.motion_project"]=("plan",motion_document_schema())


def document_contract(tool_id,input_name=None):
    if tool_id not in _SCHEMAS:
        return None
    field, schema = _SCHEMAS[tool_id]
    if input_name is not None and input_name!=field:
        schema=_SECONDARY.get(tool_id,{}).get(input_name)
        if schema is None:return None
        field=input_name
    schema = deepcopy(schema)
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    digest = hashlib.sha256(json.dumps(schema, sort_keys=True).encode()).hexdigest()
    return {"version": "zx7-document/1", "sha256": digest, "input_name": field,
            "json_schema": schema, "validation_scope": "shape and declared numeric bounds",
            "native_source_and_semantic_preflight_required": True}


def document_contracts(tool_id):
    primary=document_contract(tool_id)
    if primary is None:return {}
    return {primary["input_name"]:primary,**{
        name:document_contract(tool_id,name) for name in _SECONDARY.get(tool_id,{})}}


def validate_document(tool_id, document,input_name=None):
    contract = document_contract(tool_id,input_name)
    if contract is None:
        return False
    _validate(document, contract["json_schema"], "")
    if tool_id == "body.visual_graph":
        from .body_visual_graph import validate_graph
        validate_graph(document)
    if tool_id == "body.motion_project":
        from .body_motion_project import validate_motion_job
        validate_motion_job(document)
    return True


def _validate(value, schema, path):
    def reject(message):
        raise ValueError((path or "/") + ": " + message)
    if "oneOf" in schema:
        matches = 0
        for item in schema["oneOf"]:
            try: _validate(value, item, path)
            except ValueError: continue
            matches += 1
        if matches != 1: reject("must match exactly one supported operation")
        return
    if "enum" in schema and value not in schema["enum"]: reject("unsupported value")
    kind = schema.get("type")
    types = {"object": dict, "array": list, "string": str, "integer": int,"null":type(None),
             "boolean": bool, "number": (int, float)}
    if kind and (not isinstance(value, types[kind]) or
                 (kind in ("integer", "number") and isinstance(value, bool))):
        reject("expected " + kind)
    if kind == "object":
        missing = set(schema["required"]) - set(value)
        if missing: reject("missing " + ", ".join(sorted(missing)))
        extra = set(value) - set(schema["properties"])
        if extra and not schema.get("additionalProperties"): reject("unsupported fields " + ", ".join(sorted(extra)))
        for key, item in value.items():
            if key not in schema["properties"]:continue
            escaped = key.replace("~", "~0").replace("/", "~1")
            _validate(item, schema["properties"][key], path + "/" + escaped)
    elif kind == "array":
        if not schema.get("minItems",0) <= len(value) <= schema.get("maxItems",2**31): reject("array size")
        for i, item in enumerate(value):
            item_schema=schema["prefixItems"][i] if "prefixItems" in schema else schema["items"]
            _validate(item, item_schema, path + "/" + str(i))
    elif kind == "string":
        if len(value) < schema.get("minLength",0): reject("empty string")
        if "pattern" in schema and not re.fullmatch(schema["pattern"], value): reject("invalid format")
    elif kind in ("number", "integer"):
        if not math.isfinite(value): reject("must be finite")
        if "minimum" in schema and value < schema["minimum"]: reject("below minimum")
        if "maximum" in schema and value > schema["maximum"]: reject("above maximum")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]: reject("must be positive")
