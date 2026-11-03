# Original viewer fullscreen and capture procedure

Operation `C-A95C-DEMO3H-UI-CAPTURE-20261103-v1`; work `C57-A95C-UI-CAPTURE-PROCEDURE-20261103-v1`; original task `DEEPEYE-IMPLEMENTATION-20261014/version1`; responsible C main `01a14025-4dfd-7ec3-aebb-57be48daba59`. A95C is verified comment6597691473 by numeric328016885. Its deadline is peer context, not a new human contract. Original source baseline: `e47033f342fe76bd7a9c9284e9a3ff0e2521ff24`.

## What is ready

The existing launcher now accepts explicit `--fullscreen`, mutually exclusive with `--headless`; default launch is unchanged. Only argument parsing and Godot command construction change. The original engine/runtime/helper checks, environment isolation, Save protocol and control authority remain intact. `fullscreen-vs-C56.patch` is the portable launcher-only diff for A's own reviewed deployment. Do not copy C's local Python identity manifest over A's runtime profile.

C ran this candidate on the existing Godot4.7.2 executable, opened the previously mouse-authored C56 layout once, focused the solid drill, changed front/isometric views, zoomed outward and returned to the whole scene. Six bounded actual UI screenshots are included. No new layout Save, scene script, motion, board call, training or model test was performed. The old C56 layout is an existing visibility input, not a fixed route or replacement acceptance scene.

## Fast procedure in the original UI

1. In the left editor panel, scroll down to **相机**. Click **聚焦钻头**. This uses the actual drill mesh bounds and changes only the camera. The metal solid drill is clearly visible in `ui/03-focus-solid-drill.png`.
2. Use **前/后/左/右/顶/底/等轴测** to change view direction. These buttons retain the current target and distance; they do not automatically restore a whole-scene overview. Front and isometric changes were exercised here.
3. Place the pointer in the central 3D area to use the wheel; down zooms out, up zooms in. A wheel action was exercised here. On a side panel the wheel scrolls that panel. Original source also binds right-drag to orbit and middle-drag to pan; those two gestures were source-reviewed but **NOT_RUN in C57** because this UI tool exposes only a left-button drag. A should verify them on its live instance.
4. To restore an overview, ensure no obstacle is selected, then click **聚焦选中** (or use original `F` when the 3D view receives it), then **等轴测**. With no selection, this focuses scene centre at distance52. With an obstacle selected it focuses that obstacle. `F` is not the drill-focus shortcut. The no-selection button sequence was exercised here; `F` itself was source-reviewed only.
5. Focus-drill is a one-shot camera adjustment, not automatic following of a moving drill. Reframe during the real run as needed. Keep the actual obstacle/layout/gate proportions.
6. For a new C-local launch, use the exact reviewed launcher, explicit Godot executable and a fresh owned run directory, adding `--fullscreen`. A should apply the small launcher diff to its own reviewed source/profile and arrange its own instance lifecycle. Do not restart or open a duplicate live controller merely to change display mode. Original `Esc` requests stop; it is not an exit-fullscreen shortcut. This C test used normal Alt+F4 after visibility inspection, with viewer and launcher exits0.

## Recording the real run

Use an external recorder on A's actual UI instance. Microsoft's Windows11 Snipping Tool documents **Record → New → select the original UI region → Start → Stop → Save**. Verify A actually has this feature before beginning; this C task did not execute or validate that recorder and produced screenshots, not a video. Preserve the saved original video and its hash, and keep real run identity/timestamps with A's original evidence.

Do not use the engine Movie Maker as a substitute for a live real-time board capture: the exact installed engine's help says `--write-movie` forces `--fixed-fps`, which disables real-time synchronization. Godot's Movie Maker documentation explicitly describes non-real-time capture. An exported video or a motionless viewer is not board/control-chain completion.

Official references: [Microsoft Snipping Tool](https://support.microsoft.com/en-au/windows/apps/use-snipping-tool-to-capture-screenshots), [Godot Movie Maker](https://godotengine.org/article/movie-maker-mode-arrives-in-godot-4/). Exact engine help is in `main/engine-help.stdout`.

## Visibility blockers and minimal changes

- Original nominal scales: scene cube30m, drill diameter0.24m/length0.80m, gate nominal0.30m. Torus mesh radii are0.135/0.165m; nominal gate size is not its exact outer mesh diameter. At whole-scene distance the drill and gate rings are tiny. The existing focus button is sufficient for a clear drill close-up; no geometry or collision scaling was added.
- The blue/red gate labels and positions appear in whole-scene screenshots, but the small ring geometry is not a clear close-up in this run. **Clear gate close-up remains unverified.** This delivery does not claim all objects are simultaneously legible at every zoom level.
- `ui/05-wheel-out-label-overlap.png` shows oversized world-space text along the top of the near front view. Changing the viewing angle/distance can avoid a particular overlap; label occlusion is still a presentation defect, not fixed or accepted here. No material/model redesign was made.
- C's authority and coordinator are disconnected. The original UI truthfully disables Run/Continue and request-run. Nothing was force-enabled. A must retain its own original live objects, board authority and arrival criteria.
- Fullscreen leaves original UI sidebars and aspect-ratio letterboxing visible. It does not mean the central 3D viewport alone occupies the whole display.

## Runtime drift and exact candidate

The first C57 validation exited2 before import/launch: the old approved Python hash no longer matched. That failure is retained in `main/validate-fullscreen.*`. The current platform dependency tool reported bundle26.1026.10807 at the same Python path. A new isolated stdlib probe still reports CPython3.12.14/64-bit, but seven binary identities differ from C56. All66 required paths were observed and independently compared, while Python stdlib source bytes were unchanged. This is an explicit new local runtime candidate; the verifier was not weakened or made to auto-refresh.

`candidate-source.zip` contains43 original runtime files with the explicit fullscreen change plus C-local runtime identity changes. `candidate-manifest-v2.json` identifies all43. Relative to C57v1, only `native/layout_runtime.json` and its hash constants in `native/run_viewer.py`/`editor/layout_commit_bridge.gd` change; `runtime-v2.patch` records that exact diff. C57v1 is the unchanged C56 runtime tree plus the fullscreen diff. C56 package is already published under operation `C-A89C-REAL-MOUSE-LAYOUT-20261103-v1`; it remains sealed and read-only.

Runtime manifest SHA256: `e5beba8f3ebd63d8eac3118a876ae8dc515ae14c83b68469fe8e50d328db535a`. Current C Python executable SHA256: `f8b45d63047da9d9adf09892e4cc4317b859e86a93a478cc9616bc69d3b176e5`. Engine SHA256: `ab1824f85bfd8e0e4128182c000c4003a3e042245b2967848d089b2a04b22424`. These C machine pins are not a portable approval of A's runtime.

Actual exits: isolated probe0; v1 validate2; v2 validate0; first resource import0; viewer PID31956 exit0; launcher PID29436 exit0. Original viewer stderr is empty. The exact launch, stderr/stdout and exit record are included. There was no helper Save call, so this work adds no new helper ACK or Save acceptance.

## Evidence and remaining acceptance

Run `python -I -S -B verify_delivery.py` for a read-only hash/ZIP-member identity check. It does not start the viewer or validate functionality. The independent review checks source changes, current runtime pins, screenshots and claim boundaries; original worker completion is separately audited by the main.

Contract `DEEPEYE-HUMAN-LOCK-20261014/revision1`, source `f5989cd5defce561f9ba98e6b18fc2682945f0a2`, requirements SHA256 `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`, fixed design `1011259415a0916054eb580687612580bc1e5f09` remain unchanged. All H01–H15, original29 acceptance cards, both H12 paths, final100MHz/1%/100ms remain in scope. Actual recording, live free orbit/pan, moving-drill following, clear gate close-ups, collision/traversal, AI decisions, FPGA/board participation and formal acceptance are not established by this visibility run. A alone operates the physical board.
