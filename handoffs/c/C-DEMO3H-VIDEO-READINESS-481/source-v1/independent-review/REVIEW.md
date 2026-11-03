# C58 independent source review

Work `C58-VIDEO-READINESS-INDEPENDENT-REVIEW-v1`; task `DEEPEYE-IMPLEMENTATION-20261014/version1`; actual worker `/root/c58_ui_review`, thread `01a1a0f8-170c-71a2-ac26-932c5f733a4d`. Only this review directory is writable by this worker. Parent remains sole C main `01a14025-4dfd-7ec3-aebb-57be48daba59`.

Contract `DEEPEYE-HUMAN-LOCK-20261014/revision1`, fixed source `f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA256 `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`, design `1011259415a0916054eb580687612580bc1e5f09`. All H01–H15 remain. Identity checks do not establish acceptance.

## Independent findings

Reviewed supplied source at `d4095b9abbf27fcfe7bb66a11e4f27da2cf72ee0`. The read-only identity script confirms each of the three source files matches its exact SHA256/Git blob and confirms canonical requirements. Actual command exit 0. No product code, UI, hardware, network, test suite, or recording executed.

| Source | Confirmed behavior | Consequence |
|---|---|---|
| `ui/shell.gd:101–112,618–630` | Six stages and scalar data rows include raw, encoded, decoded, AI decision, control command, board output/readback, drill pose, cycle, scenario. `codec_mode` is displayed in the reconstruction row. | Generic encoded/board-output labels do not by themselves prove E4 or actual G05. No dedicated actual-G05 acceptance, whole-volume crossing, or obstacle-clearance row exists in this reviewed panel. |
| `ui/shell.gd:572–582` | Null, unsupported types including arrays/dictionaries, nonfinite float and blank become `未知`. Other values become text, silently limited to 160 characters. | Scrolling/wrapping cannot recover discarded content. Do not infer absent transport from an unknown display, or complete evidence from truncated text. |
| `ui/shell.gd:608–632` | Stage `observed` renders `已报告`; readiness is coordinator-ready AND connected AND no stage failed. | A reported stage is not independent success verification; enabled request is not movement acceptance. |
| `ui/shell.gd:265–269,559–570` | Right pane scrolls vertically, horizontal scrolling disabled, labels word-wrap. | Several rows need scrolling. Source alone cannot establish all rows visible simultaneously or absence of actual screen clipping. |
| `viewer/main.gd:393–412` | Drill focus changes focus point, distance and near plane once; camera-view buttons elsewhere change yaw/pitch only. | Focus is not continuous following. The camera log's literal `权威未连接` is unconditional; do not treat that log suffix as a fresh connection observation. |
| `viewer/main.gd:807–815,915–923` | Asset and gate labels billboard and disable depth testing. | Near-view overlap/obstruction is plausible. Coordinate-tick toggle is not a toggle for those labels. Runtime severity remains untested here. |
| `viewer/main.gd:179–244` | Esc requests stop; F focuses selected obstacle or scene center; RMB orbits, MMB pans, wheel changes distance. R/S can rotate/scale selected editable obstacle. | Do not use Esc as fullscreen exit or R/S as camera shortcuts. Input over UI is guarded; move pointer to central 3D area for camera operations. |
| `editor/scene_document.gd:488–509,645–656` | Gate validation checks face/center bounds and same-face overlap; route/initialization checks remain pending authority. STOP request returns acknowledged=false. | Geometry-valid and requested-stop cannot establish complete traversal or safe physical stop. |
| `viewer/main.gd:992–1006` | Owned bridge/token permits a finite authoritative pose transform and provides a readback including pose_revision. | Source mechanism alone is not evidence of actual G05-to-pose execution or feedback correspondence for a real run. |

## Limits and review state

These are source-level findings about the supplied three files, not a repository-wide claim that no other evidence exists. Do not replace unknowns with fabricated values, flatten unrelated arrays to look verified, or alter authority/collision/timing/traversal semantics for a recording. Actual runtime chronology and same-run artifact correlation must remain visible in evidence.

Final README reviewed at SHA256 `e85f2799d26a116a223ea158f10fdf38090bbaa164812c76d07b3f2b185adc6d`. No blocking issue in its bounded source-review claims. Source pins report identical reviewed UI bytes at A100 published commit `6c92f9a01bd0c6aed8b66aaef6346171e11210eb`. Independent retained-byte checks confirmed all five A100 partial files against manifest SHA256 `1e0d2510dc829cee04049bb05b42acaf1cbd44502d47b93173fc0a1543fdfd22` and their Git blobs. A's actual tested commit remains separately `2f303122f9635ce874da04a61891036ba7d579d7`. Summary explicitly reports false for AI, APPLY, motion, whole crossing and successful video, with source observations marked twin_fixture/candidate_only. Wire is 292 hexadecimal characters / 146 bytes and the reply lists four frame results; no decoder was executed.

The exact patch SHA256 is `1206645321d12d5b36f0720e6a774e64f7ab3fc9afcc597ecb30c7621435a8c5`. Independently reconstructed diff is byte-identical. Exactly two line changes: neutral camera-log text and 157-character prefix plus three dots for strings longer than 160. The latter preserves the 160-character cap and existing type/finite/blank checks, marks loss but does not recover discarded data. No producer/geometry/authority/timing/success-rule change was found. Approved as a reviewable display-only candidate; Godot import and actual display execution remain NOT_RUN and deployment is not authorized by this review.

`check_final.py` returned exit 0 and retained `checks.json`. Product acceptance, board acceptance, whole-volume traversal, 100 MHz/1%/100 ms, original 29 cards and both H12 paths remain unaccepted by this review. C56 raw-helper ACK/helper OS terminal/worker join gaps are not resolved here.

## Raw execution record

Original worker session captures all tool inputs/outputs. Source reads and identity script have returned; no launched persistent process or child agent. One early PowerShell read attempted nonexistent deployment-root contract paths; it printed missing-path errors despite aggregate exit 0. The subsequent exact-source read and canonical verification succeeded. This failed lookup is not represented as passing validation.
