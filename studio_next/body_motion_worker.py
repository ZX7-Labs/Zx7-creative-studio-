"""Host-owned Blender RNA transaction worker, executed by native Blender only."""
from __future__ import annotations
import json
from pathlib import Path
import sys


def execute(job,output,base=None):
    import bpy
    from studio_next.body_motion_project import METHODS,validate_motion_job
    validate_motion_job(job)
    if base:bpy.ops.wm.open_mainfile(filepath=str(base),load_ui=False,use_scripts=False)
    else:bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.save_version=0
    bpy.context.preferences.filepaths.use_scripts_auto_execute=False
    refs={};results=[]

    def resolve(path):
        current={"data":bpy.data,"scene":bpy.context.scene,"refs":refs}[path[0]]
        for part in path[1:]:
            if isinstance(current,dict) or type(part) is int:current=current[part]
            else:
                try:current=getattr(current,part)
                except AttributeError:current=current[part]
        return current

    def value(raw):
        if isinstance(raw,dict):return resolve(raw["$ref"])
        if isinstance(raw,list):return [value(x) for x in raw]
        return raw

    def observed(raw):
        if raw is None or type(raw) in (str,int,float,bool):return raw
        if hasattr(raw,"bl_rna"):return {"rna_type":raw.bl_rna.identifier,"name":getattr(raw,"name",None)}
        if isinstance(raw,(tuple,list)) or type(raw).__name__ in ("Vector","Color","Euler","Quaternion","bpy_prop_array"):
            return [observed(x) for x in raw]
        return {"native_type":type(raw).__name__}

    def portable():
        if bpy.data.libraries:raise ValueError("Linked external libraries must be made local before native publication")
        for group in (bpy.data.images,bpy.data.fonts,bpy.data.sounds):
            for item in group:
                filepath=getattr(item,"filepath","")
                if filepath and filepath!="<builtin>" and not getattr(item,"packed_file",None):
                    raise ValueError("External motion dependencies must be packed: "+item.name)
        if bpy.data.movieclips or bpy.data.cache_files or bpy.data.volumes:
            raise ValueError("Unsealed external footage/cache is not portable native motion data")
        for obj in bpy.data.objects:
            for modifier in obj.modifiers:
                cache=getattr(modifier,"point_cache",None)
                if cache is not None and (cache.use_external or cache.is_baked):
                    raise ValueError("External/baked simulation cache requires its own sealed dependency adapter")
        for scene in bpy.data.scenes:
            if scene.use_nodes:
                if any(n.bl_idname=="CompositorNodeOutputFile" for n in scene.node_tree.nodes):
                    raise ValueError("Render publication uses host-owned output paths")

    def define_armature_bones(obj,bones):
        from studio_next.body_motion_project import validate_armature_bones
        validate_armature_bones(bones)
        layer=bpy.context.view_layer
        if not isinstance(obj,bpy.types.Object) or obj.type!="ARMATURE":
            raise ValueError("Bone definition target must be a native armature object")
        if obj.library or obj.data.library or obj.data.users!=1 or len(obj.data.bones):
            raise ValueError("Bone definition requires empty local single-user armature data")
        if bpy.context.mode!="OBJECT":
            raise ValueError("Bone definition requires native object mode")
        # Linking a new object via RNA schedules a dependency graph update.
        # Synchronize the actual layer before checking membership or entering
        # edit mode; never permit edits to an object from another view layer.
        layer.update()
        if layer.objects.get(obj.name)!=obj:
            raise ValueError("Bone definition target is not in the active view layer")
        selected=list(bpy.context.selected_objects);active=layer.objects.active
        try:
            for item in selected:item.select_set(False)
            obj.select_set(True);layer.objects.active=obj
            if bpy.ops.object.mode_set(mode="EDIT")!={"FINISHED"}:
                raise RuntimeError("Native armature edit mode unavailable")
            edit=obj.data.edit_bones
            for spec in bones:
                bone=edit.new(spec["name"])
                if bone.name!=spec["name"]:raise ValueError("Native bone identity was changed")
                bone.head=spec["head"];bone.tail=spec["tail"];bone.roll=spec["roll"]
            for spec in bones:
                bone=edit[spec["name"]]
                if spec["parent"] is not None:bone.parent=edit[spec["parent"]]
                bone.use_connect=spec["connected"]
            if bpy.ops.object.mode_set(mode="OBJECT")!={"FINISHED"}:
                raise RuntimeError("Native armature commit failed")
        finally:
            if obj.mode=="EDIT":bpy.ops.object.mode_set(mode="OBJECT")
            for item in list(bpy.context.selected_objects):item.select_set(False)
            for item in selected:item.select_set(True)
            layer.objects.active=active
        actual=obj.data.bones
        if len(actual)!=len(bones):raise ValueError("Native bone count differs from authored topology")
        for spec in bones:
            bone=actual[spec["name"]]
            if ((bone.parent.name if bone.parent else None)!=spec["parent"] or
                bone.use_connect!=spec["connected"] or bone.length<1e-5):
                raise ValueError("Native rest hierarchy differs from authored topology")
            for point,key in ((bone.head_local,"head"),(bone.tail_local,"tail")):
                if any(abs(a-b)>max(1e-6,abs(b)*1e-6) for a,b in zip(point,spec[key])):
                    raise ValueError("Native rest coordinates differ from authored topology")
        return {"armature":obj.name,"bones":[{"name":b.name,"parent":b.parent.name if b.parent else None,
                "head":list(b.head_local),"tail":list(b.tail_local),"connected":b.use_connect} for b in actual]}

    portable()
    for index,action in enumerate(job["actions"]):
        try:
            target=resolve(action["path"]);op=action["op"]
            if op=="set":
                if len(action["path"])<2:raise ValueError("Cannot replace native root")
                parent=resolve(action["path"][:-1]);name=action["path"][-1]
                if type(name) is int:parent[name]=value(action["value"])
                else:
                    prop=parent.bl_rna.properties.get(name) if hasattr(parent,"bl_rna") else None
                    if prop is None or prop.is_readonly:raise ValueError("Target must be a writable native RNA property")
                    if getattr(prop,"subtype","") in ("FILE_PATH","DIR_PATH") or name in ("expression",):
                        raise ValueError("External paths and executable expressions are managed by the host")
                    setattr(parent,name,value(action["value"]))
                result={"changed":action["path"]}
            elif op=="call":
                method=action["method"]
                if method not in METHODS:raise ValueError("Not a native project data method")
                returned=getattr(target,method)(*value(action["args"]),**{k:value(v) for k,v in action["kwargs"].items()})
                if returned is False:raise ValueError("Native data method reported failure")
                if action["as"] is not None:refs[action["as"]]=returned
                result=observed(returned)
            elif op=="define_armature_bones":result=define_armature_bones(target,action["bones"])
            elif op=="read":result=observed(target)
            elif op=="list":
                result={"total":len(target),"items":[observed(target[i]) for i in
                    range(action["offset"],min(len(target),action["offset"]+action["limit"]))]}
            else:
                rna=getattr(target,"bl_rna",None)
                result={"native_type":type(target).__name__,"properties":[],"methods":[]}
                if rna:
                    for prop in rna.properties:
                        row={"name":prop.identifier,"type":prop.type,"readonly":prop.is_readonly,
                             "description":prop.description,"array_length":getattr(prop,"array_length",0)}
                        if prop.type=="ENUM":row["choices"]=[e.identifier for e in prop.enum_items]
                        result["properties"].append(row)
                result["methods"]=[m for m in METHODS if callable(getattr(target,m,None))]
                if rna:result["native_functions"]=[f.identifier for f in rna.functions]
            results.append({"index":index,"op":op,"result":result})
        except Exception as exc:raise ValueError(f"Native action {index} ({action['op']}) failed: {exc}") from exc
    portable()
    output=Path(output);renders=[]
    # Native file stays the authoritative editable project; render settings
    # are temporarily overridden only for the host-controlled output transport.
    bpy.ops.wm.save_as_mainfile(filepath=str(output/"project.blend"),compress=False)
    for index,item in enumerate(job["renders"]):
        scene=bpy.data.scenes[item["scene"]]
        scene.frame_set(item["frame"])
        settings=scene.render;settings.use_file_extension=True
        settings.image_settings.color_mode="RGBA"
        suffix="png" if item["format"]=="png" else "exr"
        settings.image_settings.file_format="PNG" if suffix=="png" else "OPEN_EXR"
        settings.image_settings.color_depth="8" if suffix=="png" else "32"
        if suffix=="exr":settings.image_settings.exr_codec="ZIP"
        file=f"render_{index:06d}.{suffix}";settings.filepath=str(output/file)
        bpy.ops.render.render(write_still=True,scene=scene.name)
        if not (output/file).is_file():raise RuntimeError("Native engine did not write requested render")
        decoded=bpy.data.images.load(str(output/file),check_existing=False)
        expected=(settings.resolution_x*settings.resolution_percentage//100,settings.resolution_y*settings.resolution_percentage//100)
        if tuple(decoded.size)!=expected or not decoded.has_data:raise RuntimeError("Native render failed actual image decode")
        bpy.data.images.remove(decoded)
        renders.append({**item,"file":file,"width":settings.resolution_x*settings.resolution_percentage//100,
                        "height":settings.resolution_y*settings.resolution_percentage//100})
    report={"engine_version":bpy.app.version_string,"actions":results,"renders":renders,
            "objects":[{"name":x.name,"type":x.type} for x in bpy.data.objects],
            "scenes":[x.name for x in bpy.data.scenes]}
    (output/"native.json").write_text(json.dumps(report,allow_nan=False))
    return report


if __name__=="__main__":
    # Blender launches a script rather than an installed host interpreter.
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    args=sys.argv[sys.argv.index("--")+1:]
    execute(json.loads(Path(args[0]).read_text()),args[1],args[2] if len(args)>2 else None)
