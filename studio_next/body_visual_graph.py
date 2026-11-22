"""Editable native photo/motion/VFX graph; float32 linear-sRGB associated alpha.

Nodes are creative project data, never new BODY code. Pixel expressions expose
straight channels. Spatial sampling and convolution filter associated channels
to preserve transparent edges. No supplied style or effect recipe is selected.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math
import re
from .body_animation import curve_value, validate_curve
from .body_pixel_math import BASE_VARIABLES, FUNCTION_ARITY, PixelExpression

_NAME=re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
_CHANNELS="rgba"


@dataclass(frozen=True)
class VisualBudget:
    """Host resource policy; not artistic style, duration or template selection."""
    max_pixels:int=16777216
    max_nodes:int=1024
    max_frames:int=24000
    max_live_bytes:int=1024**3
    max_kernel_side:int=63
    max_expression_work:int=4000000000
    max_source_frames:int=240000
    max_decode_bytes:int=8*1024**3


def _exact(value,fields,label,optional=()):
    if (not isinstance(value,dict) or not set(fields).issubset(value)
            or not set(value).issubset(set(fields)|set(optional))):
        raise ValueError(label+" has missing or unsupported fields")


def _integer(value,label,minimum=0):
    if type(value) is not int or value<minimum:
        raise ValueError(label+" must be an integer >= "+str(minimum))
    return value


def _uniforms(value):
    if not isinstance(value,dict):raise ValueError("Uniform controls must be a named object")
    for name,signal in value.items():
        if (not isinstance(name,str) or not _NAME.fullmatch(name)
                or name in BASE_VARIABLES or name in FUNCTION_ARITY):
            raise ValueError("Invalid/reserved uniform name")
        validate_curve(signal)


def validate_graph(plan,*,budget=None):
    budget=budget or VisualBudget()
    _exact(plan,("version","canvas","nodes","output","render"),"Visual graph")
    if plan["version"]!="zx7-visual-graph/1":raise ValueError("Unsupported visual graph version")
    c=plan["canvas"]
    _exact(c,("width","height","frame_rate","frames","working_space"),"Canvas")
    w=_integer(c["width"],"width",1);h=_integer(c["height"],"height",1)
    count=_integer(c["frames"],"frames",1)
    _exact(c["frame_rate"],("numerator","denominator"),"Frame rate")
    for key,value in c["frame_rate"].items():_integer(value,key,1)
    if c["working_space"]!="linear_srgb":raise ValueError("Explicit linear_srgb working primaries required")
    if w*h>budget.max_pixels or count>budget.max_frames:raise ValueError("Canvas exceeds host pixel/frame resource budget")
    r=plan["render"]
    _exact(r,("first_frame","frame_count","format","rgb_range","audio"),"Render")
    first=_integer(r["first_frame"],"first_frame");length=_integer(r["frame_count"],"frame_count",1)
    if first+length>count:raise ValueError("Render interval exceeds the original project clock")
    if r["format"] not in ("png","rgba_mov","exr32") or (r["format"] in ("png","exr32") and length!=1):
        raise ValueError("Still images select one frame; rgba_mov preserves an interval")
    expected_range="preserve_float" if r["format"]=="exr32" else "clip_to_sdr"
    if r["rgb_range"]!=expected_range or r["audio"]!="separate_tracks":
        raise ValueError("Export range and separate-track audio decisions must match the format")
    if not isinstance(plan["nodes"],list) or not 1<=len(plan["nodes"])<=budget.max_nodes:
        raise ValueError("Graph is empty or exceeds host node budget")
    indexed,compiled={},{};work=0
    for node in plan["nodes"]:
        _exact(node,("id","op","inputs","params"),"Node")
        name=node["id"]
        if not isinstance(name,str) or not _NAME.fullmatch(name) or name in indexed:
            raise ValueError("Invalid or duplicate node identity")
        indexed[name]=node
        inputs,p,op=node["inputs"],node["params"],node["op"]
        if not isinstance(inputs,dict) or any(not isinstance(k,str) or not _NAME.fullmatch(k)
                or not isinstance(v,str) for k,v in inputs.items()):
            raise ValueError("Node inputs require named graph references")
        expressions={}
        if op=="source":
            if inputs:raise ValueError("Source nodes do not consume graph inputs")
            _exact(p,("media","kind","color_space","frame"),"Source",("alpha_mode","channels"))
            _exact(p["media"],("source","asset_id","attestation_id"),"Source custody")
            if p["kind"] not in ("image","video") or p["color_space"] not in ("srgb","bt709","linear_srgb"):
                raise ValueError("Source requires declared kind and supported transfer function")
            if p["color_space"]=="linear_srgb":
                if p["kind"]!="image" or p.get("alpha_mode") not in ("straight","associated"):
                    raise ValueError("Float EXR source requires explicit alpha association")
                if "channels" in p:
                    _exact(p["channels"],_CHANNELS,"EXR channel selection")
                    if any(not isinstance(v,str) or not 1<=len(v)<=255 for v in p["channels"].values()):
                        raise ValueError("Invalid EXR channel name")
            elif "channels" in p or "alpha_mode" in p:
                raise ValueError("Explicit channel/alpha declarations belong to float EXR sources")
            validate_curve(p["frame"])
            if p["kind"]=="image" and p["frame"]!=0:raise ValueError("Still images have only frame zero")
        elif op in ("expression","remap"):
            expected=("channels","uniforms") if op=="expression" else ("x","y","uniforms","filter","border")
            _exact(p,expected,op);_uniforms(p["uniforms"])
            if op=="remap" and "image" not in inputs:raise ValueError("Remap requires an image input")
            names=set(BASE_VARIABLES)|set(p["uniforms"])
            for port in inputs:
                for channel in _CHANNELS:
                    variable=port+"_"+channel
                    if variable in names:raise ValueError("Input channel collides with a uniform name")
                    names.add(variable)
            if op=="expression":
                _exact(p["channels"],_CHANNELS,"Output channels");raw=p["channels"]
            else:
                if p["filter"] not in ("nearest","bilinear") or p["border"] not in ("transparent","clamp","wrap"):
                    raise ValueError("Unknown spatial sampling policy")
                raw={k:p[k] for k in ("x","y")}
            expressions={key:PixelExpression(value,names) for key,value in raw.items()}
            work+=sum(e.node_count for e in expressions.values())
        elif op=="over":
            _exact(inputs,("foreground","background"),"Over inputs")
            _exact(p,("opacity",),"Over controls");validate_curve(p["opacity"])
        elif op=="convolve":
            _exact(inputs,("image",),"Convolution inputs")
            _exact(p,("kernel_x","kernel_y","divisor","border"),"Convolution controls",("channels",))
            if p.get("channels","rgba") not in ("rgb","rgba"):
                raise ValueError("Convolution channels must be rgb or rgba")
            for key in ("kernel_x","kernel_y"):
                values=p[key]
                if not isinstance(values,list) or not len(values) or len(values)%2!=1 or len(values)>budget.max_kernel_side:
                    raise ValueError("Convolution requires odd kernels within host resource budget")
                for value in values:validate_curve(value)
                work+=len(values)
            validate_curve(p["divisor"])
            if p["border"] not in ("transparent","clamp","wrap"):raise ValueError("Unknown convolution edge policy")
        else:raise ValueError("Unknown native graph primitive: "+str(op))
        compiled[name]=expressions
    if work*w*h>budget.max_expression_work:raise ValueError("Graph exceeds host pixel-math work budget per frame")
    if not isinstance(plan["output"],str) or plan["output"] not in indexed:
        raise ValueError("Graph output must identify an existing node")
    order,active,done=[],set(),set()
    def visit(name):
        if name not in indexed:raise ValueError("Missing input node: "+name)
        if name in active:raise ValueError("Cyclic visual graph")
        if name in done:return
        active.add(name)
        for parent in indexed[name]["inputs"].values():visit(parent)
        active.remove(name);done.add(name);order.append(name)
    try:visit(plan["output"])
    except RecursionError as exc:raise ValueError("Graph exceeds host dependency depth") from exc
    if set(indexed)!=done:raise ValueError("Unused nodes must be removed or connected to the authored output")
    return indexed,order,compiled


def to_linear(rgb,space="srgb"):
    import numpy as np
    if space=="srgb":return np.where(rgb<=.04045,rgb/12.92,((rgb+.055)/1.055)**2.4).astype(np.float32)
    return np.where(rgb<.081,rgb/4.5,((rgb+.099)/1.099)**(1/.45)).astype(np.float32)


def from_linear(rgb):
    import numpy as np
    rgb=np.clip(rgb,0,1)
    return np.where(rgb<=.0031308,12.92*rgb,1.055*rgb**(1/2.4)-.055)


def associate(rgba):
    result=rgba.copy();result[...,:3]*=result[...,3:4]
    return result


def straight(rgba):
    import numpy as np
    result=rgba.copy()
    np.divide(rgba[...,:3],rgba[...,3:4],out=result[...,:3],where=rgba[...,3:4]>0)
    result[...,:3]=np.where(rgba[...,3:4]>0,result[...,:3],0)
    return result


def sample_image(image,x,y,*,method,border):
    """Inverse source pixel-center coordinates; first center is (.5,.5)."""
    import numpy as np
    h,w=image.shape[:2]
    if border=="wrap":x,y=np.mod(x-.5,w)+.5,np.mod(y-.5,h)+.5
    else:x,y=np.clip(x,-1,w+1),np.clip(y,-1,h+1)
    def fetch(ix,iy):
        if border=="wrap":return image[iy%h,ix%w]
        pixel=image[np.clip(iy,0,h-1),np.clip(ix,0,w-1)]
        if border=="transparent":pixel=pixel*((ix>=0)&(ix<w)&(iy>=0)&(iy<h))[...,None]
        return pixel
    if method=="nearest":return fetch(np.floor(x).astype(np.int64),np.floor(y).astype(np.int64))
    x,y=x-.5,y-.5
    x0,y0=np.floor(x).astype(np.int64),np.floor(y).astype(np.int64)
    dx,dy=(x-x0)[...,None],(y-y0)[...,None]
    return ((1-dx)*(1-dy)*fetch(x0,y0)+dx*(1-dy)*fetch(x0+1,y0)
            +(1-dx)*dy*fetch(x0,y0+1)+dx*dy*fetch(x0+1,y0+1)).astype(np.float32)


def _convolve(image,kernels,border,*,backend="numpy"):
    """Separable native filtering with a host-selected and attested backend.

    Existing NumPy numerics remain the default. Optional SciPy executes the
    SAME artist-authored kernels using compiled ndimage.convolve1d; no image
    becomes an 8-bit Pillow intermediate and no color/alpha contract changes.
    The output backend is recorded by the physical renderer for reproducibility.
    """
    import numpy as np
    if backend=="scipy":
        from scipy.ndimage import convolve1d
        edge={"transparent":"constant","clamp":"nearest","wrap":"wrap"}[border]
        # Convolution, not correlation: preserve asymmetric signed kernels.
        result=image
        for axis,weights in ((1,kernels[0]),(0,kernels[1])):
            result=convolve1d(result,weights,axis=axis,mode=edge,cval=0.,
                              output=np.float32)
        return result
    if backend!="numpy":
        raise ValueError("Unsupported visual convolution backend")
    result=image
    for axis,weights in ((1,kernels[0]),(0,kernels[1])):
        radius=len(weights)//2;padding=[(0,0)]*3;padding[axis]=(radius,radius)
        padded=np.pad(result,padding,mode={"transparent":"constant","clamp":"edge","wrap":"wrap"}[border])
        output=np.zeros_like(image)
        for i,weight in enumerate(reversed(weights)):
            section=[slice(None)]*3;section[axis]=slice(i,i+image.shape[axis])
            output+=weight*padded[tuple(section)]
        result=output
    return result


class VisualGraph:
    def __init__(self,plan,*,budget=None,convolution_backend="numpy"):
        # The host opts in explicitly. A project's original JSON remains
        # independent of installed wheels and creative-model suggestions.
        if convolution_backend not in ("numpy","scipy"):
            raise ValueError("Unsupported visual convolution backend")
        if convolution_backend=="scipy":
            try:
                from scipy.ndimage import convolve1d  # noqa: F401
            except ImportError as exc:
                raise RuntimeError("Selected SciPy visual engine is not installed") from exc
        self.convolution_backend=convolution_backend
        self.budget=budget or VisualBudget()
        self.plan=json.loads(json.dumps(plan,allow_nan=False))
        self.nodes,self.order,self.compiled=validate_graph(self.plan,budget=self.budget)
        self.canvas=self.plan["canvas"]
        r=self.canvas["frame_rate"];self.fps=Fraction(r["numerator"],r["denominator"])

    def frame(self,frame_index,*,source_provider=None):
        import numpy as np
        _integer(frame_index,"original frame")
        if frame_index>=self.canvas["frames"]:raise ValueError("Frame is outside the original project clock")
        h,w=self.canvas["height"],self.canvas["width"]
        if h*w*4*4*16>self.budget.max_live_bytes:raise ValueError("Frame working set exceeds host memory budget")
        yy,xx=np.mgrid[:h,:w].astype(np.float32)
        base={"x":xx+.5,"y":yy+.5,"u":(xx+.5)/w,"v":(yy+.5)/h,"width":np.float32(w),
              "height":np.float32(h),"frame":np.float32(frame_index),"time":np.float32(Fraction(frame_index)/self.fps),"pi":np.float32(math.pi)}
        values={}
        refs=Counter(parent for node in self.nodes.values() for parent in node["inputs"].values())
        refs[self.plan["output"]]+=1
        for name in self.order:
            node=self.nodes[name];op=node["op"];p=node["params"]
            inputs={port:values[parent] for port,parent in node["inputs"].items()}
            env=dict(base)
            if op in ("expression","remap"):
                env.update({key:np.float32(curve_value(signal,frame_index)) for key,signal in p["uniforms"].items()})
                needed=set().union(*(expr.names for expr in self.compiled[name].values()))
                for port,pixels in inputs.items():
                    if any(port+"_"+c in needed for c in _CHANNELS):
                        if pixels.shape!=(h,w,4):raise ValueError("Explicitly remap source dimensions before channel arithmetic")
                        unassociated=straight(pixels)
                        for i,c in enumerate(_CHANNELS):env[port+"_"+c]=unassociated[...,i]
                evaluated={key:np.broadcast_to(expr.evaluate(env),(h,w)) for key,expr in self.compiled[name].items()}
            if op=="source":
                if source_provider is None:raise ValueError("Source node requires the sealed native media decoder")
                requested=curve_value(p["frame"],frame_index)
                if not math.isfinite(requested) or requested<0 or abs(requested-round(requested))>1e-6:
                    raise ValueError("Source sampling requires a nonnegative exact source frame")
                rgba=np.asarray(source_provider(name,int(round(requested))),dtype=np.float32)
                if rgba.ndim!=3 or rgba.shape[2]!=4 or rgba.shape[0]*rgba.shape[1]>self.budget.max_pixels:
                    raise ValueError("Decoded source geometry exceeds host policy")
            elif op=="expression":rgba=associate(np.stack([evaluated[c] for c in _CHANNELS],axis=-1))
            elif op=="remap":rgba=sample_image(inputs["image"],evaluated["x"],evaluated["y"],method=p["filter"],border=p["border"])
            elif op=="over":
                foreground,background=inputs["foreground"],inputs["background"]
                if foreground.shape!=background.shape:raise ValueError("Composite dimensions differ; author an explicit remap")
                opacity=curve_value(p["opacity"],frame_index)
                if not 0<=opacity<=1:raise ValueError("Animated opacity left the physical alpha range")
                fg=foreground*opacity;rgba=fg+background*(1-fg[...,3:4])
            else:
                kernels=[[curve_value(k,frame_index) for k in p[key]] for key in ("kernel_x","kernel_y")]
                divisor=curve_value(p["divisor"],frame_index)
                if not math.isfinite(divisor) or divisor==0:raise ValueError("Convolution divisor must be finite and nonzero")
                rgba=_convolve(inputs["image"],kernels,p["border"],
                               backend=self.convolution_backend)/divisor
                if p.get("channels","rgba")=="rgb":rgba[...,3]=inputs["image"][...,3]
            if not np.all(np.isfinite(rgba)) or np.min(rgba[...,3])< -1e-6 or np.max(rgba[...,3])>1+1e-6:
                raise ValueError("Node "+name+" produced invalid finite RGBA/alpha")
            rgba=np.asarray(rgba,dtype=np.float32);rgba[...,3]=np.clip(rgba[...,3],0,1)
            values[name]=rgba
            if sum(v.nbytes for v in values.values())+h*w*4*4*16>self.budget.max_live_bytes:
                raise ValueError("Graph live buffers exceed host memory budget")
            for parent in node["inputs"].values():
                refs[parent]-=1
                if not refs[parent]:del values[parent]
        result=values[self.plan["output"]]
        if result.shape!=(h,w,4):raise ValueError("Output dimensions require an explicit authored remap")
        return result

    def node_fingerprints(self):
        """Project dependencies only; not physically verified render-cache hits."""
        hashes={}
        for name in self.order:
            node=self.nodes[name]
            value={"canvas":self.canvas,"node":node,"dependencies":{port:hashes[parent] for port,parent in node["inputs"].items()}}
            hashes[name]=hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()
        return hashes


def revision_impact(before,after):
    old,new=VisualGraph(before),VisualGraph(after)
    a,b=old.node_fingerprints(),new.node_fingerprints()
    return {"changed_or_dependent_nodes":sorted(k for k in b if a.get(k)!=b[k]),
        "unchanged_project_nodes":sorted(k for k in b if a.get(k)==b[k]),"removed_nodes":sorted(set(a)-set(b)),
        "output_selection_changed":old.plan["output"]!=new.plan["output"],
        "render_selection_changed":old.plan["render"]!=new.plan["render"],"physical_cache_reuse_verified":False}


def rgba8(premultiplied):
    import numpy as np
    value=straight(premultiplied)
    clipped=int(np.count_nonzero((value[...,:3]<0)|(value[...,:3]>1)))
    value[...,:3]=from_linear(value[...,:3])
    return np.rint(np.clip(value,0,1)*255).astype(np.uint8),clipped
