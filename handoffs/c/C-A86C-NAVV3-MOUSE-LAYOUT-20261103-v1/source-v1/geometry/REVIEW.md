# C55 short adjacent-face geometry fixture

Task/version `DEEPEYE-IMPLEMENTATION-20261014/1`; work `C55-NAVV3-GEOMETRY-CPU-VECTORS-20261103-v1`. Exact A source `e47033f342fe76bd7a9c9284e9a3ff0e2521ff24`. Contract `DEEPEYE-HUMAN-LOCK-20261014/revision1`, source `f5989cd5defce561f9ba98e6b18fc2682945f0a2`; canonical requirements SHA256 `c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804`; all H01–H15 retained. Fixed design remains `1011259415a0916054eb580687612580bc1e5f09`.

This is a generated, **not_mouse_authored / software_fixture** layout and a narrowly scoped standard-library CPU geometry check. It is not a mouse-authored scene, engine-codec test, reachable-path proof, 16-actor result, actual board result or acceptance. It contains no planned route, commands, fabricated observations or runtime identity. Main owns delivery and independent review.

## Exact artifact and scene parameters

`layout-software-fixture.json` is the proposed private simulator/Root layout input. Its original generated UTF-8 bytes have SHA256 `46857169649885c16a1200c840f8919ceddc1fda4e34ac78b834b4c4a2013813`. The different `layout_hash` field is the canonical geometry commitment `dca69ff201e0f347599faaa445156f0d9c11faf56a3510c058c9fa8dbafdbeb2`. Do not substitute one hash for the other. Metadata/provenance is deliberately a sidecar (`parameters.json`), not unsupported fields inside the strict layout file.

| Item | Serialized parameters | Meaning |
|---|---|---|
| Blue entry | `face=top, u=12, v=0` | Centre `(12,15,0)`, outward `+Y`, inward drilling `-Y` |
| Red exit | `face=right, u=0, v=12` | Centre `(15,12,0)`, outward `+X` |
| Both gates | Source-fixed radius **0.15 m**, diameter **0.30 m** | Radius/diameter are not additional layout fields |
| Water | object 1, position `(8,9,0)`, size `(3,2,1)`, rotations zero, priority 2 | Nominal box `[6.5,9.5]×[8,10]×[-.5,.5]` |
| Hard rock | object 2, position `(10,10,0)`, size `(1,1,1)`, rotations zero, priority 1 | Nominal box `[9.5,10.5]×[9.5,10.5]×[-.5,.5]` |
| Initial proposal | explicit outward standoff **0.60 m** | Body origin `(12,15.6,0)`; original `initial_pose_for_layout` supplies the top-face inward quaternion and zero initial speed |
| Drill envelope | segment half-length `.4 m`, radius `.12 m` | Diameter `.24 m`, capsule total length `1.04 m`; not a point drill |

The gate centres are each 3 m from the shared top/right edge. This is a short adjacent-face candidate, **not a proven globally shortest scene or a computed path**. Original `integration/motion.py:29–35,57–74` bounds combined curvature by 0.5/m, giving radius at least 2 m for nonzero curvature. Choosing a 3 m corner offset avoids implying that the editor's 0.15 m edge allowance accommodates a full turning drill. This scale argument does not establish a clear swept trajectory, exact quantized steering, enough stopping distance, a successful AI decision or sufficient 16-command budget. No trajectory was generated or supplied. Obstacles are present in the actual layout; the check does not prove that the eventual causal route will encounter/avoid them meaningfully. That remains an online demonstration requirement.

## Layout format and integration

All source references in this report are under `competition/deepeye/` at the exact commit above; `source-pins.json` contains full SHA256/Git blob/byte identities for the 19 relevant original files checked locally against main's archive manifest. Main separately verified all 8542 blobs; this worker does not claim to have repeated that whole-tree audit.

`simulator/editor/layout_codec.gd:13–39,70–115,117–193,195–210,254–290,341–365` requires exactly:

```text
schema, contract, requirements_sha256, units, layout, layout_hash
layout: obstacles, gates
obstacle: object_id, kind, position{x,y,z}, rotation_deg{x,y,z}, size{x,y,z}, priority
gates: entry{face,u,v}, exit{face,u,v}
```

Schema is 1, units `m`, contract string includes `/revision1`, positive unique object IDs and kind-matching priorities are mandatory. The fixture retains water and hard rock, with valid minimum dimensions, zero rotation and full nominal boxes inside ±15 m. The codec itself only checks obstacle centres against ±15 m; the additional full-box check here is a useful conservative property of these particular parameters, not a claim that its codec contains the stronger rule. The gate fields permit ±14.85, same-face circles may not overlap, and both colours use the same fixed radius. The actual authority additionally checks exact binary64 radius-plus-edge inequalities (`motion/workspace_boundaries.py:66–79`).

Canonical layout hash is sorted JSON with `LayoutCodec._canon`'s number formatting, not SHA256 of the whole pretty-printed file. This fixture deliberately uses only integral geometry, so normalized float `String.num(...,6)` and the supplied integer canonical form agree without relying on a generic cross-language float formatter. The NEW CPU check reads the actual saved file and rechecks this restricted-domain commitment. **Godot encode/decode was not executed**, so the named canonical roundtrip check is not an engine roundtrip claim. A should import via original `SceneDocument.apply_layout_text()` (`scene_document.gd:388–425`) and retain original save bytes/hash through `export_layout_text():380–383` and `LayoutStore.save_new[_async]():52–78`. Successful import replaces geometry only, clearing old edit/selection history; it cannot restore link/AI/authority state. A needs a real fresh mouse-edit/save record for the requested mouse-authored stage, even if these numeric parameters are used as a guide. Re-exported bytes may differ and require their own raw hash.

The file and obstacle locations go only through the simulator/Root private layout channel. Do not send its body, truth map, seed, screenshot or precomputed geometric queries to FPGA or PC inference. Public gate/drill values are distinct from this private obstacle layout. This CPU fixture is an offline parameter review, not online control input.

## Entry: newly published capability versus actual local blocker

The main's `ui-availability-v1.json` reports no Godot/DeepEye in supported windows/apps, PATH or searched accessible directories, with WindowsApps access denied retained. This worker did not repeat the scan, install an engine or interact with UI/security dialogs. It records **local original UI unavailable; actual mouse evidence absent**, rather than claiming no possible installation exists on the machine.

Unlike the prior A999 source, e470's `_owned_godot.py:27–40,90–91,132–139` includes exact `ApprovedLaunchSpec.visible_demo_v1: bool=False`. True explicitly omits `--headless`, omits CREATE_NO_WINDOW and selects SW_SHOW; false preserves original behavior. The command still selects `res://runtime/owned_world_start.gd`. This published source feature is available for A to integrate, not a local run result. A must retain its actual approved engine/project hashes, original lifecycle/bootstrap, layout bytes and private output setup; this fixture cannot supply those identities.

`tools/run_causal_functional_chain.py:184–197,218–246` now explicitly accepts `navigation_profile=None` and passes a validated navigation selection into original acquisition and source construction. Use the actual typed original profile and factory; a JSON label is not authority. `simulator/viewer/main.gd:15,21,137–143` still has a separate demo request signal and disabled legacy Run semantics; the selected owner driver, original board/AI path, movement and returned state must actually execute. Main/sibling owns the deeper chain/freshness review; this geometry report neither declares all UI plumbing blocked nor claims an owner-loop connection just from the button or visible window.

## External red goal is not red centre + 0.05 m

`simulation/authority/g05_csr_projection_v1.py:16–37,213–216` builds the public goal from:

```text
red centre + outward normal ×
  (actual half_segment + actual radius + actual numeric bound + actual asset bound + 0.05)
```

It computes exact rational sums of supplied original values, converts the active coordinate, then applies `nextafter` outward. For this right gate the X coordinate is strictly beyond `15 + .4 + .12 + numeric + asset + .05`; Y is 12 and Z is 0. It is **not** `(15.05,12,0)`. `parameters.json` retains the formula. Its example of numeric=.001 and asset=.001 gives approximately `(15.572000000000003,12,0)`; this is a clearly marked synthetic CPU budget example, not a production error bound or recommended replacement policy.

Actual bounds come from original snapshot-derived `_world_values.py:1217–1265`: complete mesh/shape inventory and original drill correspondence, capsule envelope, `numeric=GUARD+actual getter cap`, `asset=GUARD+actual drill containment residual`, and obstacle residual. Its GUARD is 1e-6 m. The original initializer uses all relevant errors and certifies actual initial body/scene and gate corridors. This task has no original engine snapshot, measured containment, getter cap or certified budgets, so it does not assign those facts. The three .001 CPU assumptions merely make the boundary examples concrete.

For the proposed .60 m initial standoff, the nominal `.4+.12=.52 m` axial extent leaves approximately .08 m before additional errors/guards. For the gate, `.15-.12=.03 m` is only a nominal radial clearance; actual whole-slice rotation, curvature/chord, endpoint/export and asset uncertainty also consume it. `motion/gate_clearance.py:216–246` uses an inflated strict radial inequality and directed angle; touching the ring is not safe. Do not convert either nominal margin into a blanket permitted error cap.

Original static inner alignment corridors are one-metre-long radius-.15 cylinders, centred half a metre inward (`_world_values.py:1028–1052`). The CPU check uses enclosing AABBs for these particular axis-aligned gates. AABB strict separation with the declared synthetic combined margin is sufficient for this fixture's nominal boxes; failure of that simple check is not a general collision proof. The explicit negative obstacle at the blue corridor actually intersects it and is refused by the fixture. Production must run its original pair certifier and actual error budgets.

Full red exit is the **entire** inflated drill outside the selected red face, the other five faces still inside as appropriate, valid aperture/continuous slice proofs and ordered passage history. `motion/passage_phase.py:72–108,154–172,200–231` requires INITIAL_OUTSIDE→ENTRY_WINDOW→ENTERED→EXIT_WINDOW→ARRIVED and retains final-slice/suffix checks. A public target or a centre outside a plane proves none of that. The CPU negative vectors include red-centre-only, centre+.05, radial tangency and a body outside the red plane but laterally away from its gate. Even a safe isolated final pose cannot be relabelled as an actual exit history.

## NavV3 budget and 16 fresh decisions

`navigation_session_profile.py:6–14,17–45,88–109` supplies the actual declared values. Their logical SHA was independently recomputed from AST-read literal tuple and the declared domain, without importing or executing the module:

- Profile `DEEPEYE-NAV-ADJACENT-180S-V3`, logical SHA256 `5a3679f80be3668aaa1765ecdb157776f38c661ce1bb9d40d5dac8b447967d17`.
- 180s duration, 1s source period, max 16 commands and 16 scans, 100ms maximum STEP, 3000ms maximum command TTL.
- Public rolling selection limit is **24**, not 32; original private journals remain under their separate 1001-source/2048-book caps. Current original observation must survive selection.

These are finite interface limits, not evidence of 16 actual fresh observations, calls, original actors or completed commands. Sixteen reused messages, holding one command for multiple STEPs, fixture labels or a profile hash cannot satisfy that execution target. Original actual board result/source association, selected original AI package, command slot/expiry, motion, returned progress and final fences remain necessary. This worker generated zero commands and zero actor decisions. Main/sibling reviews those deep production relationships separately. Static parameter validity does not prove that sixteen actual decisions can complete a curved path around obstacles or that the deadline is achievable.

## NEW evidence and exact scope

One new standalone `geometry_fixture.py` was run by `run_fixture.py` with a 30s subprocess bound. Original `run01.command.json`, `run01.stdout`, `run01.stderr` retain argv, source version, timestamps, raw streams and actual exit **0**. The source SHA is `2cee808a4e66b8fc8528328c9ca0994e0696913c950e8c103a84ace0492654b5`. Eighteen narrow positive/negative checks passed, recorded individually in `geometry-results.json`: restricted serialization/hash, adjacent gates and edge next-float boundary, nominal obstacle volumes, inner corridor separation/intersection, initial whole-body support and too-short standoff, radial tangency, and complete-support external-goal versus false point/offset/lateral claims. This was the only CPU fixture run; no earlier suite was replayed. No product imports, original codec execution, engine, model, PDE, Root, native, board or service operation occurred.

`source-pins.json` distinguishes source file SHA from logical profile SHA and verifies 19 selected original files against exact manifest bytes/Git blobs. Canonical H01–H15 was recomputed at 4680 bytes and matched the fixed hash. Native tool evidence preserves earlier read/search errors (memory search no hits; guessed paths absent) and output truncation; none was presented as successful product validation. No software fixture result is promoted to A's reported CPU9/actor4serial, actual board load, mouse editing, full red exit or final acceptance.

Next necessary action is on A's authorized original environment: use/import the proposed parameters or mouse-author equivalent layout, retain its real UI/save bytes and exact launch/profile/source evidence, obtain original snapshot-derived budgets, then run the actual bounded board→AI→whole-drill loop with truthful failure/quality reporting. Keep stage shortcomings and both final H12 paths unaccepted until their own evidence exists. No repeated failed side effects, credential changes or second owner are authorized by this file.
