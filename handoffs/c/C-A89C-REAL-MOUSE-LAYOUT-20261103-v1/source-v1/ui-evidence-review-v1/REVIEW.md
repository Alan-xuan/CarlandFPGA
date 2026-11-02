# C56 actual UI evidence independent review

Bounded result: PASS for retained evidence of original local viewer editing, original Save success indication and exact resulting JSON, followed by normal viewer/launcher exit. The evidence does not satisfy a claim that raw helper ACK, helper OS child termination or internal worker-join records were independently captured. Those three records are absent. No source, model, route, board or final human acceptance is conferred by this review.

Work C56-ACTUAL-UI-EVIDENCE-REVIEW-20261103-v1, task DEEPEYE-IMPLEMENTATION-20261014 version 1. Independent reviewer /root/c28_independent_review, actual thread 01a18686-39ad-75d3-8bb4-90836d2ac026. Only this new review directory was written. Main's UI/source and previous reviews remain unchanged.

## Observed evidence

All ten original screenshots were opened with view_image. Initial image shows the empty original viewer. Images 02/03/04 show adding water, initial selection/drag with no coordinate change, then moved water. Images 05/06 show added hard rock and its moved/selected state. Visible inspector values round for display; exact saved coordinates are water (-3.25, 0.0, 8.5) and hard rock (9.75, 0.0, 1.5). The first non-moving water attempt remains visible and is not rewritten as success.

Images 07/08 show entry on top (+Y) with displayed u=12 and exit on right (+X) with displayed v=12, respectively blue/red marks on adjacent faces. These are face/geometry settings, not a tested traversable route. Image 09 shows the original Save-as dialog and target; image 10 shows the original success hint “已另存为新文件（仅几何）”. The viewer simultaneously labels authority/control/model paths as unconnected and does not display a full-chain success.

The original main session's bounded 18:25–18:33 UTC interval contains actual sky.drag calls for both objects, UI face/coordinate input, one original Save click, and closing the selected viewer with Alt-F4. Exact call records are retained, with raw-output record hashes and the original screenshots. The reviewed ui-actions.jsonl records one save submission to a previously absent path. The screenshot series and original call records support actual UI manipulation; this review did not replay it.

Original main/ui/mouse-layout.json is 1265 bytes, SHA256 `6b6caf18d6dfb61df23db1f29fda3a33f6f7f47395803090185f103a0488dbbe`. It contains the two expected objects, top/right face settings, the unchanged contract and requirements digest. Decimal parsing independently preserves entry.u and exit.v exactly as `12.000000000000002`; neither input nor copied evidence was reserialized or rounded. The embedded layout_hash is `d332d8560efb210d7e7866bd2a038a652f4ce5b2beb35d82ce3ace38a76c6d18`. That internal commitment was recorded, not re-executed through Godot or represented as a signature. Exact file bytes are the independently verified artifact identity.

Viewer stdout records CHILD_PID=22868 and CHILD_EXIT=0. Viewer stderr is empty. The launcher record is PID 39864, exit 0. Launch argv selects the reviewed base Python, pinned non-console Godot, main-owned runtime copy and private run directory. The 43 declared source files still match the reviewed manifest after UI: 40 match original e470 bytes; the two code files differ only in runtime hash strings, and the third change is the explicit local runtime manifest. Generated cache files are not claimed original source or part of this 43-file invariant.

## Missing records and source-derived implications

The attempted CIM observer failed at Register-CimIndicationEvent with original tool exit 1 and “调用已取消”. The exact original tool text is retained. Its JSONL contains only observer_closed, not observer_ready or a helper start/stop event. It was not retried. Neither viewer exit 0 nor observer_closed is helper termination evidence.

The unchanged shell:969–984 reports success only after stored.ok from LayoutStore. Previously reviewed unchanged bridge:249–280 requires valid matching DLR1 result, original exit 0 and committed/publication_confirmed state; :296–300 joins the completed owner worker before reaped; :347–355 returns only after unresolved becomes false. These are implications of the frozen original source plus the observed UI success. There is no independently captured raw ACK, operation ID, original helper exit record or evidence() record in this UI run. Bridge:309–319 also explicitly does not certify native CloseHandle success. Do not claim direct observation of those facts or full ACK/terminal acceptance.

## Correction and scope

Original ui-main-verification-v1.json mislabeled the full candidate manifest hash as runtime_manifest_sha256. Main preserved that original and added ui-evidence-correction-v1.json. Both were independently checked: candidate-manifest-v2.json is `c06a2ff583f3dba2c46b5bd1a86ef863298d09b6fbb2cd7b8c40dd2ce2ca1218`; native/layout_runtime.json is `91772ca86c66866d86fb073ec4e7c6b06c1e904b10d067fa77716df69f123d71`. This is a corrected evidence label, not an altered saved layout or product repair. No remaining blocker to the bounded truthful UI report; missing ACK/child records remain explicit limits.

Independent check_evidence.py exited 0 and performs only file/JSON/hash checks, source byte comparison and bounded reading of original session evidence. Reviewer product/UI/engine/helper/model/board executions: 0; reviewer product exit: null/NOT_RUN. The original observer exit 1 remains distinct from the independent check exit 0 and the original viewer/launcher exits 0. H01–H15, both H12 requirements, fixed contract/design, A-only board responsibility and uncompleted formal acceptance remain unchanged.

Evidence copies preserve exact original bytes and input-pins.json identifies their sources. Own raw tool logs/exit index and freeze accompany FINAL. No background jobs or subprocesses were created by the reviewer; ownership is released on FINAL. Main must audit the finalizer's actual closing output and this task_complete after this response.
