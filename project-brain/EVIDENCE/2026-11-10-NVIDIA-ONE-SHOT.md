# NVIDIA Super VL 120B — one-shot negative forensic evidence

Date: **2026-11-10**, synthetic-only host approval; [GitHub run #42754872382](https://github.com/ZX7-Labs/Zx7-creative-studio-/actions/runs/42754872382). Actual checkout `76104b4f177ad1eb99e0cb17c8fee194d0d6193e` and model `nvidia/nemotron-3.5-super-vl-120b-a12b`. **Completed failure**, not a creative acceptance. This report contains no credential, private owner media, or copied prompt.

## Custody

- GitHub artifact ID `13735184585` (limited retention), 22 allowlisted objects; independently downloaded ZIP SHA-256: `09b2a2cce1d92ecdb12a55458d8b73abe981c70f619210a1ff89e5ee16302e9f`.
- Actual source generated locally with FFmpeg and approved for cloud visual observation. Existing NVIDIA credential was present for the real run. No 429/rate-limit evidence.
- Session recorded 112 journal events: 47 native operations submitted, 40 result records, 13 post-write host observations, 2 host pre-dispatch rejections, 1 model-output recovery record at **turn 21: `truncated_tool_decision`**, no native dispatch. The difference between submitted and returned counts is **not** seven accepted operations; avoid inferring missing writes.

## Independent ffprobe of all five saved MP4 paths

| Saved path | Actual video | Duration | Audio streams | Full SHA-256 |
|---|---|---|---|---|
| `momentum_640x360_first.mp4` | H.264 1920×1080 24/1fps | 6.000s | 0 | `1ea56346d0b47f381bc3b5383d5c1a8ae4360ebf93ddd665f788236c15a7777b` |
| `momentum_640x360_v1.mp4` | Same | 6.000s | 0 | `1ea56346d0b47f381bc3b5383d5c1a8ae4360ebf93ddd665f788236c15a7777b` |
| `momentum_small_changes_v1.mp4` | H.264 1920×1080 24/1fps | 6.000s | 0 | `1b561f6d9fe23a3ff6b6c16d1086b410343a59f2a118cf6e65906bfec64586fc` |
| `momentum_v1.mp4` | Same as first | 6.000s | 0 | `1ea56346d0b47f381bc3b5383d5c1a8ae4360ebf93ddd665f788236c15a7777b` |
| `momentum_v1_640x360.mp4` | Same as first | 6.000s | 0 | `1ea56346d0b47f381bc3b5383d5c1a8ae4360ebf93ddd665f788236c15a7777b` |

The owner's synthetic brief specified H.264 **640×360**, 24 fps, ≤6s. Filename alone does **not** establish delivered dimensions. Two unique video byte digests, **zero** fully accepted brief-conformant outputs. No audio track was delivered and there is no basis to claim listening. A real model-observed frame and subsequent edit are **partial neural evidence**, not completion.

## Root cause and corrective work

1. Model-originated provider-native `truncated_tool_decision` at turn 21 was already rejected *without native dispatch* by the controller; independent audit permitted only five local JSON error codes. #292 (merged `c41a705f7e199e57a573ce28ee486b822af5a05d`) unifies the 23 finite admissible model-output rejection categories, maintaining max two corrections, strictly increasing turns, no pending native write, true no-dispatch and no quality certification. Targeted source/native/MLT tests passed; cancelled unrelated render check does not count.
2. Source-backed Velorn MCP `electron/mcpServer.js` defaults export delivery target to `h264_hd` (1920×1080) when no proper native resolution is selected. The model used 640×360 project settings but native exports were HD. #293 proposes **optional owner-owned delivery guard**: inspect true pinned `check_export_readiness.deliveryTarget` prior to any export write; reject wrong dimensions/FPS/codec/duration while preserving other owners' explicit HD exports.
3. Still required: neural model chooses correct work and meets all gates with independent physical audio/picture/edited project proofs and professional critique. No new hosted run occurred for the fixes.

## Evidence integrity limits

GitHub retained artifact may expire. Public source logs redact the API credential. This record preserves SHA references and negative technical facts, **not** model quality certification. Revalidate exact PR status and source against current GitHub; do not infer implementation/merges from a proposed patch.
