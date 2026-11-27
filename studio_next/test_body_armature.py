"""Native armature topology admission and actual editable skin deformation proof."""
from __future__ import annotations
import copy
import json
import math
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile
from studio_next.body_motion_project import VERSION, validate_motion_job, motion_runtime_ready, digest, verify_motion_bundle
from studio_next.body_document_schemas import validate_document
from studio_next.body_integration import run_body_project


def rig_action():
    return {"op":"define_armature_bones","path":["refs","Rig"],"bones":[
        {"name":"Tip","head":[0,1,0],"tail":[0,2,0],"roll":0,"parent":"Root","connected":True},
        {"name":"Root","head":[0,0,0],"tail":[0,1,0],"roll":0,"parent":None,"connected":False}]}


def job(actions):
    return {"version":VERSION,"project":None,"actions":actions,"renders":[]}


class ArmatureContractTests(unittest.TestCase):
    def test_unordered_valid_bone_hierarchy(self):
        plan=job([rig_action()])
        self.assertEqual(validate_motion_job(plan),plan)
        self.assertTrue(validate_document("body.motion_project",plan))

    def test_invalid_topology_and_numeric_values_fail_before_native_process(self):
        def check(mutate):
            action=copy.deepcopy(rig_action());mutate(action)
            with self.assertRaises(ValueError):validate_motion_job(job([action]))
            with self.assertRaises(ValueError):validate_document("body.motion_project",job([action]))
        for mutate in (
            lambda a:a["bones"][0].update(parent="Unknown"),
            lambda a:a["bones"][1].update(parent="Unknown"),
            lambda a:a["bones"][1].update(parent="Tip"),
            lambda a:a["bones"][0].update(name="Root"),
            lambda a:a["bones"][0].update(tail=[0,1,0]),
            lambda a:a["bones"][0].update(head=[0,1.1,0]),
            lambda a:a["bones"][1].update(connected=True),
            lambda a:a["bones"][0].update(roll=float("inf")),
            lambda a:a["bones"][0].update(head=[False,1,0]),
            lambda a:a["bones"][0].update(name="é"*32),
            lambda a:a["bones"][0].update(name="bad\nname"),
            lambda a:a.update(bones=[]),
            lambda a:a.update(path=["refs","_secret"]),
        ):
            with self.subTest(mutate=mutate):check(mutate)


def skin_job():
    actions=[]
    def call(path,method,args=(),kwargs=None,alias=None):
        actions.append({"op":"call","path":path,"method":method,"args":list(args),"kwargs":kwargs or {},"as":alias})
    def set_(path,value):actions.append({"op":"set","path":path,"value":value})
    def ref(name):return {"$ref":["refs",name]}
    def object_(name,data):
        call(["data","objects"],"new",[name,ref(data)],alias=name)
        call(["scene","collection","objects"],"link",[ref(name)])
    call(["data","armatures"],"new",["Skeleton"],alias="skeleton")
    object_("Rig","skeleton");actions.append(rig_action())
    call(["data","meshes"],"new",["Skin"],alias="mesh")
    call(["refs","mesh"],"from_pydata",[[[-.25,1,0],[.25,1,0],[.25,2,0],[-.25,2,0]],[],[[0,1,2,3]]])
    object_("Character","mesh")
    call(["refs","Character","vertex_groups"],"new",kwargs={"name":"Tip"},alias="weights")
    call(["refs","weights"],"add",[[0,1,2,3],1.0,"REPLACE"])
    call(["refs","Character","modifiers"],"new",["SkinDeformation","ARMATURE"],alias="skin")
    set_(["refs","skin","object"],ref("Rig"))
    pose=["refs","Rig","pose","bones","Tip"]
    set_(pose+["rotation_mode"],"XYZ")
    for frame,angle in ((1,0),(5,math.pi/2)):
        set_(pose+["rotation_euler"],[0,0,angle])
        call(pose,"keyframe_insert",kwargs={"data_path":"rotation_euler","frame":frame})
    return job(actions)


@unittest.skipUnless(motion_runtime_ready(),"Actual Blender 4.5+ required")
class NativeSkinProof(unittest.TestCase):
    def test_native_rig_skin_pose_and_revision_survive_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            original=skin_job();revision=job([{"op":"set","path":["data","objects","Rig","pose","bones","Tip","rotation_euler"],"value":[0,0,-math.pi/2]},
                {"op":"call","path":["data","objects","Rig","pose","bones","Tip"],"method":"keyframe_insert","args":[],"kwargs":{"data_path":"rotation_euler","frame":5},"as":None}])
            revision["project"]="original.zxmotion"
            for name,plan in (("original",original),("revision",revision)):
                (root/(name+".json")).write_text(json.dumps(plan))
            graph=[{"id":name,"tool_id":"body.motion_project","purpose":"Native skin deformation engineering control", "inputs":{"plan":name+".json","out":name+".zxmotion"},"depends_on":deps} for name,deps in (("original",[]),("revision",["original"]))]
            result=run_body_project({"project":{"creative_intent":"Native rig topology and skin control"},"shots":[{"id":"rig","purpose":"Technical control probe"}],"tool_graph":graph},root)
            self.assertEqual(result["status"],"all_tool_results_verified",result)
            first=verify_motion_bundle(root/"original.zxmotion");second=verify_motion_bundle(root/"revision.zxmotion")
            self.assertEqual(second["parent_bundle_sha256"],digest(root/"original.zxmotion"))
            script=root/"observe.py"
            script.write_text('''import bpy,json,sys\nfrom pathlib import Path\nargs=sys.argv[sys.argv.index("--")+1:]\nbpy.ops.wm.open_mainfile(filepath=args[0],load_ui=False,use_scripts=False)\nrig=bpy.data.objects["Rig"];mesh=bpy.data.objects["Character"]\nassert rig.type=="ARMATURE" and rig.data.bones["Tip"].parent.name=="Root" and rig.data.bones["Tip"].use_connect\nassert len(mesh.vertex_groups)==1 and mesh.vertex_groups[0].name=="Tip" and mesh.modifiers[0].object==rig\nframes=[]\nfor frame in (1,5):\n bpy.context.scene.frame_set(frame)\n ev=mesh.evaluated_get(bpy.context.evaluated_depsgraph_get());m=ev.to_mesh()\n frames.append([list(ev.matrix_world@v.co) for v in m.vertices]);ev.to_mesh_clear()\nPath(args[1]).write_text(json.dumps(frames))\n''')
            for name,sign in (("original",1),("revision",-1)):
                with zipfile.ZipFile(root/(name+".zxmotion")) as archive:
                    blend=root/(name+".blend");blend.write_bytes(archive.read("project.blend"))
                output=root/(name+"-observed.json")
                proc=subprocess.run(["blender","--background","--factory-startup","--disable-autoexec","--threads","2","--python-exit-code","1","--python",str(script),"--",str(blend),str(output)],capture_output=True,text=True,timeout=120)
                self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
                frames=json.loads(output.read_text());rest=[[-.25,1,0],[.25,1,0],[.25,2,0],[-.25,2,0]]
                expected=[rest,[[-sign*(y-1),1+sign*x,z] for x,y,z in rest]]
                for actual,wanted in zip(frames,expected):
                    for a,b in zip(actual,wanted):
                        for x,y in zip(a,b):self.assertAlmostEqual(x,y,places=5)
