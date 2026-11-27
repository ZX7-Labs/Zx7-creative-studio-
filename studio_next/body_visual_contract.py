"""Machine-readable authoring grammar for native creative project controls."""


def visual_graph_contract():
    def obj(fields):return {"type":"object","required":list(fields),"properties":fields,"additionalProperties":False}
    def enum(*values):return {"enum":list(values)}
    def arr(item,**bounds):return {"type":"array","items":item,**bounds}
    def mapping(item):return {"type":"object","required":[],"properties":{},"additionalProperties":item}
    text={"type":"string","minLength":1};number={"type":"number"}
    integer={"type":"integer","minimum":0};positive={"type":"integer","minimum":1}
    key=obj({"frame":number,"value":number})
    cubic=obj({"frame":number,"value":number,"in_slope":number,"out_slope":number})
    signal={"oneOf":[number,obj({"interpolation":enum("hold","linear"),"keys":arr(key,minItems=1)}),
        obj({"interpolation":enum("cubic_hermite"),"keys":arr(cubic,minItems=1)})]}
    source=obj({"source":text,"asset_id":{"type":"string","pattern":"^[0-9a-f]{64}$"},"attestation_id":text})
    border=enum("transparent","clamp","wrap")
    def node(kind,inputs,params):return obj({"id":text,"op":enum(kind),"inputs":inputs,"params":params})
    source_params=obj({"media":source,"kind":enum("image","video"),"color_space":enum("srgb","bt709","linear_srgb"),"frame":signal})
    source_params["properties"].update(alpha_mode=enum("straight","associated"),channels=obj({key:text for key in "rgba"}))
    point=arr(signal,minItems=2,maxItems=2)
    segment=obj({"control1":point,"control2":point,"end":point})
    contour=obj({"start":point,"segments":arr(segment,minItems=1,maxItems=512)})
    nodes=[node("source",obj({}),source_params),
        node("expression",mapping(text),obj({"channels":obj({key:text for key in "rgba"}),"uniforms":mapping(signal)})),
        node("remap",mapping(text),obj({"x":text,"y":text,"uniforms":mapping(signal),"filter":enum("nearest","bilinear"),"border":border})),
        node("over",obj({"foreground":text,"background":text}),obj({"opacity":signal})),
        node("convolve",obj({"image":text}),obj({"kernel_x":arr(signal,minItems=1),"kernel_y":arr(signal,minItems=1),"divisor":signal,"border":border}))]
    nodes[-1]["properties"]["params"]["properties"]["channels"]=enum("rgb","rgba")
    nodes.append(node("path_mask",obj({"image":text}),obj({"contours":arr(contour,minItems=1,maxItems=512),
        "fill_rule":enum("evenodd","nonzero"),"invert":{"type":"boolean"}})))
    schema=obj({"version":enum("zx7-visual-graph/1"),"canvas":obj({"width":positive,"height":positive,
        "frame_rate":obj({"numerator":positive,"denominator":positive}),"frames":positive,"working_space":enum("linear_srgb")}),
        "nodes":arr({"oneOf":nodes},minItems=1),"output":text,"render":obj({"first_frame":integer,"frame_count":positive,
        "format":enum("png","rgba_mov","exr32"),"rgb_range":enum("clip_to_sdr","preserve_float"),"audio":enum("separate_tracks")})})
    schema["description"]=("Editable native pixel graph, never executable software. Expressions use + - * / ** %, single comparisons, "
        "sin cos tan sqrt abs exp log floor ceil min max atan2 pow clamp mix where smoothstep. Variables: x/y pixel centers "
        "(first .5), u/v normalized centers, width height frame time pi, authored uniforms and <input>_r/g/b/a straight linear channels. "
        "Remap x/y are inverse source coordinates. Curve endpoints hold; cubic slopes are value per original frame. "
        "Path masks have authored animated cubic control points in canvas pixels, implicit straight closure, explicit winding rule and inversion; preserve associated alpha. "
        "Frames are zero-based; time is seconds at rational fps. Native validation checks graph, math and host budgets. "
        "Float32 linear-sRGB internals. Explicit sRGB 16-bit PNG source codes and alpha are preserved before graph math; unsupported color profiles are refused. "
        "exr32 exports preserve_float RGBA; EXR input requires linear_srgb and explicit alpha_mode, "
        "optional RGBA channel names; data-window local coordinates. PNG/MOV export is 8-bit SDR with explicit clip_to_sdr. "
        "Original clock preserved; audio remains separate tracks.")
    return schema
