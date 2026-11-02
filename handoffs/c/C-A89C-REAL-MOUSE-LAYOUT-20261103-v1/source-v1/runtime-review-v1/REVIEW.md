# C56 independent runtime packaging review

Decision: bounded static approval of main's explicit local C packaging v2, runtime manifest SHA256 `91772ca86c66866d86fb073ec4e7c6b06c1e904b10d067fa77716df69f123d71`. No blocking packaging discrepancy remains in the reviewed change. This is permission to proceed within the already authorized main-owned local UI work, not evidence that UI, Save, native helper, model, board, or final human acceptance has run or passed.

Task DEEPEYE-IMPLEMENTATION-20261014 version 1; work C56-UI-RUNTIME-INDEPENDENT-REVIEW-20261103-v1. Original A source is e47033f342fe76bd7a9c9284e9a3ff0e2521ff24. Human contract DEEPEYE-HUMAN-LOCK-20261014 revision 1, requirements c229834bfc2292f5fe4411fc9f12c68487008f9d1adaf31f0144ee7a98173804 and fixed design 1011259415a0916054eb580687612580bc1e5f09 remain unchanged. Both H12 obligations, original H01-H15, original 29 requirements, A-only physical board and uncompleted formal acceptance remain in force.

## Exact change and compatibility evidence

The 43-file subset was independently matched to the verified original Git blob/SHA/byte index. Forty files are byte-identical. The only code changes are one RUNTIME_SHA256 string in editor/layout_commit_bridge.gd:14 and one in native/run_viewer.py:15. The third changed file is native/layout_runtime.json. The v1 patch was reconstructed exactly; the v2 source was compared byte-for-byte to v1, and an independent exact delta is retained. The v2 main manifest is c06a2ff583f3dba2c46b5bd1a86ef863298d09b6fbb2cd7b8c40dd2ce2ca1218. All 61 author freeze entries remain unchanged.

The helper CLI, Windows leaf, bundle, bootstrap hex, environment whitelist, viewer logic, geometry, collision, truth/motion/passage gates and Save transport are unchanged. Original helper and leaf hashes match the original bundle. The 24 literal load/preload/serialized/initial-scene references have existing targets. This does not establish Godot's generated class cache or render initialization; main must establish those on its own writable copy.

The existing local base CPython 3.12.14 executable is 64-bit, with prefix equal to base_prefix. The author's real isolated -I -S -B stdlib-only probe exited 0; its argv, source and raw output were read. No private A venv or qualification is inherited. Independently hashed all 65 probe-listed local dependencies, plus the necessary UTF-16-LE codec. The final list has 66 pins. Both installed Godot executable byte hashes and official release asset digest metadata were checked. This is a bounded dependency inventory and local packaging profile, not a proof of every future lazy import, OS dependency, runtime behavior or trustworthiness of the whole machine.

Native/run_viewer.py:22-60 retains the real executable/prefix/base_prefix binding, exact Godot/runtime/dependency/bundle checks, and child environment isolation. Its default launch is visible, shell=False, with the original project and private run directory; --validate-only remains an explicit no-launch path. The main run command selects the pinned non-console Godot executable. The original helper only imports standard-library modules; neither NumPy nor model dependencies are needed for Save. No product module was imported by this reviewer.

## Review observations and disposition

1. The v1 probe captures modules already imported, and initially omitted the UTF-16-LE codec needed at native/layout_commit_windows.py:76,84,95,188. Its actual local source exists. Main's v2 explicitly adds the original file pin `3aedaf3eb49769282daef1eaedfd4fa1c31fe5eebeff67fe2307c89dc2e2fd80`, updates the two hash constants, and accurately limits dependency claims. This was a static inventory gap, not a demonstrated failed Save or product test RED. Closed in v2 without changing helper semantics.
2. The first independent audit overmatched every quoted res:// string, including runtime/owned_world_start.gd:35's separately supplied owned-input/layout.json. That file is dynamic input to another original owned startup path, not a load/preload resource for this viewer launch. The first script/trace and exit 1 are retained. Restricting the audit to actual resource-loading/initial-scene references produced exit 0. This is reviewer verification-script correction, not a product fix or product RED.

## Truthful Save and terminal evidence boundary

UI shell.gd:969-984 displays “已另存为新文件（仅几何）” only after the original save_new_async returns stored.ok. LayoutStore calls the unchanged bridge. Bridge:249-280 requires valid framing, original helper exit 0, matching operation_id/payload SHA/byte count, leaf_called, committed/publication_confirmed and empty close_errors. Bridge:296-300 joins the completed owner thread before marking reaped, and :347-355 returns the result only when unresolved is false.

Consequently a genuine observed success hint, the exact file readback, and independently correlated parent/child process start/exit observations can support a bounded account of actual UI acceptance and process termination. The ACK association and worker join are then source-derived implications, not directly captured ACK bytes/operation_id or internal evidence(). An OS process exit event alone cannot establish those protocol facts.

Bridge:309-319 attempts original process-map cleanup after observing exit, but explicitly does not verify kernel CloseHandle return values. Even a successful UI hint cannot certify every native handle close. The UI's last_file_result omits the full bridge record. Do not label externally observed terminal evidence as an extracted bridge record, or infer cleanup success from absence of an OS process. No out-of-scope product instrumentation is needed or approved here.

## Validation and limits

Independent work consists only of read-only source/AST/hash/resource checks and own evidence writes. Static-audit raw exits are 1 (overbroad checker), 0 (corrected checker), 0 (v2 narrow audit); original author stdlib probe exit 0 is separately attributed. The review does not rerun author product tests or old suites. Product imports 0, product/UI/engine/native/model/board runs 0; product exit code null/NOT_RUN. No background process, service or polling task was launched. Actual human mouse interaction, saved JSON, child completion and viewer termination remain main-owned follow-on evidence.

Review ownership is released on FINAL. Source pins, raw native tool records, exact command/exit index, scripts and original failure evidence are retained under this review directory. Main must independently audit this review's final synchronous command and actual task completion; the finalizer's raw-session snapshot cannot include its own later output.
