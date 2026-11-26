# Super VL bounded response recovery — actual G1 failure → documented provider boundary

**Evidence classification:** source-backed correction candidate, real provider READ-only function smoke, **NOT** full autonomous artistic acceptance.

## Real failure, without inferred creative success

- Genuine one-use [NVIDIA Super VL run #45731089541](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45731089541) returned a retained redacted journal [artifact #15078171115](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45731089541/artifacts/15078171115), independently downloaded and CRC-checked, ZIP SHA-256 `47c46e631c1cd6e691199d906a3c4ab4c5e1134573ad049f335b61fd328c35f0`.
- There were 88 events, source imports and model-selected native edits, **zero exported films**. Native tool-function output was truncated on turns **24** and **35**; after the existing two bounded no-dispatch corrections, turn **36** raised `LocalModelOutputError`. No editor write was automatically retried. The result disproves any claim that this model is already an accepted full-G1 Brain.
- Unlike raw token limits, NVIDIA's published hosted [model API](https://docs.api.nvidia.com/nim/reference/nvidia-nemotron-3_5-super-vl-120b-a12b-infer) explicitly defines `reasoning_effort: none` as disabling reasoning tokens. The existing low-effort mode and 8192-token ceiling can still end without a complete function selection. This is not a license to increase the source's overall cost/turn limits.

## Scope of the minimal source correction

- Test-first RED source `abe8ef7a56e3919cbec9d55ccfca417dbd74b8ea` reproduced exactly two failures when a **trusted no-native-dispatch truncated tool output** was followed by the same low-reasoning setting.
- GREEN source `ca1fde6e8d50fa6f9df357c9cac0596b2201b963` changed only `studio_next/nvidia_native_tool_model.py` and its existing test. Offline run [#45735067219](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45735067219) first confirmed RED and then **218 tests passed** including existing NVIDIA transport, model parser, native decision control, and real-trial request safety.
- On a provider **Super VL only** and only if current trusted host output feedback has `reason_code = truncated_tool_decision`, `no_native_dispatch = true`, and a remaining correction budget of **0 or 1**, the *one next model response* uses documented `reasoning_effort: none`. All ordinary turns retain their configured reasoning; unrelated errors, Ultra/Omni providers and direct context with non-trusted feedback do not switch the mode. Source model settings remain unchanged and no editor action is selected or executed automatically.
- A separate precisely scoped **one actual hosted provider call** [#45735473685](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45735473685) used a single synthetic text-only `get_project` function, **zero native connection or media upload**. The returned function contract was accepted, 488 input + 55 output tokens (provider reported), one request; [artifact #15078253437](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45735473685/artifacts/15078253437) ZIP SHA-256 `f9c51754bd3c632bed2883459d39cabd790ba3919c02c78a5af5c1da04291b5e`, ZIP CRC pass, retained summary agrees.
- An earlier workflow setup-only [#45735409878](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/45735409878) was rejected by the local request parser (lower-case JSON boolean in Python). It **never reached the hosted provider**. Exact-scope syntax was corrected at one-use source `50ca0d9c69a22d23fc11157df39d48e6681f4d70`, not hidden.

## Separation of proof

The successful provider *read-function contract* does not show the model can choose a valuable edit, reliably perceive semantic audio, complete a saved two-export native A/V revision, collaborate with a human, or create independent professional quality. Do not report G1–G4 or A–L complete; do not repeat unchanged model trials. A genuine native-editor acceptance requires a distinct, explicitly authorized source-pinned synthetic run with physical source/revision/sound receipts, then independently reviewed craft and release.
