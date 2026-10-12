"""C-side participation runner for the A_OFFLINE phase (one-shot, bounded).

Round MESH-20261011-132845-c94f2686; task
MESH-20261011-132845-c94f2686-controlled-cohort-C / v1; work
C-A_OFFLINE-participation-v1; nonce AF_c94f2686_e184b176.

Modes
-----
--prepare
    Unarmed contract admission.  Durable exclusive claim; real capture of the
    original C service through the cohort prepare_standby.capture() (own PID
    creation/parent, original Task fingerprint, specific original Job
    isolation); frozen prepare-ready.json; wait for the exact A->C contract
    inbound row to be truly completed + processed; exactly one
    CONTRACT_ACCEPTED report to A through the original resident outbox; then a
    bounded read-only wait for its transport terminal state and exit.  No
    standby, no ARM, no GO/probe, no service mutation.

--execute --go-payload-sha256 <64 lowercase hex>
    Byte-exact admission of the stored A->C participant-GO inbound against the
    given raw UTF-8 payload hash; require true completion + a fully idle local
    ledger; fresh original-service capture and local resident health.  Signed
    HMAC GET /v1/health samples of peer A every 2 s: first a valid signed-200
    baseline, later three consecutive transport-unreachable samples after the
    announced stop window.  Then two exact sends to B through the original
    resident (GO, then probe), each behind its own durable exclusive claim.
    The exact B->C probe inbound, its real model turn (exact ACK, persisted
    route) and processed state are required while A stays unreachable, plus a
    fresh unreachable sample after that completion.  On A's signed-200
    restoration exactly one collect receipt goes to A.  No acceptance PASS is
    declared: the outcome is a measured candidate or INCOMPLETE.

Safety envelope (both modes)
----------------------------
* Whole-lifetime local-monotonic bound (<= 600 s, from the frozen contract);
  every I/O bounded; SQLite opened read-only (mode=ro); no second HttpPeer or
  controller; no model calls; no Task registration; no service stop/start; no
  source/config mutation.
* Durable xb+fsync claims precede the execution admission and every send;
  unknown outcomes are never replayed; candidate/INCOMPLETE/timeout/failure
  outcomes are written once and immutably.
* 401/403, wrong node/project identity, invalid JSON or any other
  non-transport HTTP answer is not an outage and fails closed.

Interface notes (assumptions recorded for parent review)
--------------------------------------------------------
* contract.json and parent-review.json live in this directory (OUT).  The
  review may use {"program_sha256", "contract_sha256"} or the launch_once-style
  {"hashes": {...}}; every listed file is hash-verified at admission and again
  before each side effect.
* CONTRACT_ACCEPTED text is "CONTRACT_ACCEPTED " + one compact JSON object;
  the collect receipt is one compact JSON object with a "receipt" marker.
* The B->C inbound text must be exactly "Reply exactly ACK_AF_B_C_..."; its
  real main run result text must be exactly the ACK token.
* The node config used only for the signed A health probe is resolved as
  state_dir.parents[1]/node-c.toml, the node-root layout implied by the
  resident discovery glob (<root>/.local/deployment/node-*/.local/node-*);
  it is loaded only when --execute needs the peer A URL and HMAC secret, and
  the secret value is never written or logged.
"""
import argparse
import asyncio
import hashlib
import hmac
import json
import os
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True

OUT = Path(__file__).resolve().parent
COHORT = OUT.parent
ROOT = COHORT.parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(COHORT))

from fpga_mesh.child_control import LocalControlFileClient  # noqa: E402
from fpga_mesh.project_cli import discovery  # noqa: E402
import prepare_standby  # noqa: E402

ROUND = "MESH-20261011-132845-c94f2686"
TASK_ID = ROUND + "-controlled-cohort-C"
WORK_ID = "C-A_OFFLINE-participation-v1"
NONCE = "AF_c94f2686_e184b176"
PHASE = "A_OFFLINE"
PROJECT = "fpga-main"

CONTRACT_MESSAGE_ID = "C:" + ROUND + "-A-C-A_OFFLINE-contract-v1"
GO_OP = ROUND + "-A-C-A_OFFLINE-participant-GO-v1"
GO_MESSAGE_ID = "C:" + GO_OP
ACCEPTED_OP = ROUND + "-C-A_OFFLINE-contract-accepted-v1"
RECEIPT_OP = ROUND + "-C-A_OFFLINE-collect-receipt-v1"

COHORT_B_TASK = ROUND + "-controlled-cohort-B"
GO_TO_B_OP = ROUND + "-C-B-A_OFFLINE-GO-v1"
GO_TO_B_TEXT = "GO_A_OFFLINE " + NONCE
PROBE_TO_B_TASK = ROUND + "-A_OFFLINE-C-to-B-probe"
PROBE_TO_B_OP = ROUND + "-A_OFFLINE-C-to-B-probe-v1"
PROBE_TO_B_TEXT = "Reply exactly ACK_AF_C_B_c94f2686_e184"

PROBE_INBOUND_TASK = ROUND + "-A_OFFLINE-B-to-C-probe"
PROBE_INBOUND_ID = "C:" + ROUND + "-A_OFFLINE-B-to-C-probe-v1"
PROBE_INBOUND_TEXT = "Reply exactly ACK_AF_B_C_c94f2686_e184"
PROBE_ACK = "ACK_AF_B_C_c94f2686_e184"

MAX_SECONDS = 600
SAMPLE_SECONDS = 2.0
UNREACHABLE_REQUIRED = 3
PROBE_TIMEOUT_SECONDS = 2.0
CONTROL_TIMEOUT_SECONDS = 30.0
HEALTH_TIMEOUT_SECONDS = 20.0
MAIN_WAIT_SECONDS = 30.0
RECEIPT_MIN_REMAINING_SECONDS = 20.0

STATE_DB = "state.sqlite"
SESSIONS_DB = "main_sessions.sqlite"
CHILDREN_DB = "child_jobs.sqlite"

PREPARE_CLAIM = "prepare-claim-v1.json"
PREPARE_READY = "prepare-ready.json"
ACCEPTED_CLAIM = "contract-accepted-claim-v1.json"
PREPARE_DELIVERY = "prepare-delivery-v1.json"
EXECUTE_CLAIM = "execute-claim-v1.json"
EXECUTE_CAPTURE = "execute-capture-v1.json"
SAMPLES_LOG = "a-health-samples-v1.jsonl"
GO_CLAIM = "go-send-claim-v1.json"
PROBE_CLAIM = "probe-send-claim-v1.json"
B_EVIDENCE = "b-to-c-evidence-v1.json"
RECEIPT_CLAIM = "collect-receipt-claim-v1.json"
RECEIPT_DELIVERY = "collect-receipt-delivery-v1.json"
EXECUTE_OUTCOME = "execute-outcome-v1.json"
EXECUTE_TIMEOUT = "execute-timeout-v1.json"
PREPARE_FAILURE = "prepare-failure-v1.json"
EXECUTE_FAILURE = "execute-failure-v1.json"

ARTIFACT_ORDER = (
    "participate.py", "contract.json", "parent-review.json", "launch_once.py",
    PREPARE_CLAIM, PREPARE_READY, ACCEPTED_CLAIM, PREPARE_DELIVERY,
    EXECUTE_CLAIM, EXECUTE_CAPTURE, SAMPLES_LOG, GO_CLAIM, PROBE_CLAIM,
    B_EVIDENCE, RECEIPT_CLAIM, RECEIPT_DELIVERY, EXECUTE_OUTCOME,
    EXECUTE_TIMEOUT, PREPARE_FAILURE, EXECUTE_FAILURE,
)


class Refused(Exception):
    """Fail-closed refusal; written once as an immutable failure record."""

    def __init__(self, status, detail):
        super().__init__(status + ": " + str(detail)[:300])
        self.status = status
        self.detail = str(detail)[:300]


class BudgetExhausted(Exception):
    """The whole-lifetime local-monotonic bound ran out."""

    def __init__(self, stage):
        super().__init__("bounded wait exhausted: " + str(stage))
        self.stage = str(stage)


def utc_now():
    return datetime.now(timezone.utc)


def utc_iso():
    return utc_now().isoformat()


def timestamp(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("ISO-8601 UTC text required")
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timezone required")
    return parsed.astimezone(timezone.utc)


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def sha256_hex(data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def is_hex64(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def exclusive(path, value):
    """Durable exclusive create; FileExistsError means no replay."""
    with Path(path).open("xb") as stream:
        stream.write(compact(value).encode("utf-8") + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def exclusive_final(path, value):
    """One-shot record that must not block failure reporting."""
    try:
        exclusive(path, value)
        return str(path)
    except FileExistsError:
        fallback = Path(path).with_name(Path(path).stem + "-" + str(os.getpid()) + ".json")
        exclusive(fallback, value)
        return str(fallback)


def append_jsonl(path, value):
    with Path(path).open("ab") as stream:
        stream.write(compact(value).encode("utf-8") + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def resident_call(client, action, arguments, timeout):
    """Bounded call on the original resident loopback control channel."""

    async def invoke():
        return await client.call(action, arguments)

    return asyncio.run(asyncio.wait_for(invoke(), timeout=timeout))


class Ledgers:
    """Read-only (mode=ro) access to the original resident's SQLite ledgers."""

    def __init__(self, state_dir):
        state_dir = Path(state_dir)
        self.state_dir = state_dir
        self.state = self._connect(state_dir / STATE_DB)
        self.sessions = self._connect(state_dir / SESSIONS_DB)
        self.children = self._connect(state_dir / CHILDREN_DB)

    @staticmethod
    def _connect(path):
        if not Path(path).is_file():
            raise FileNotFoundError("ledger not found: " + str(path))
        return sqlite3.connect(
            Path(path).resolve().as_uri() + "?mode=ro", uri=True, timeout=5,
        )

    def close(self):
        for connection in (self.state, self.sessions, self.children):
            try:
                connection.close()
            except Exception:  # noqa: BLE001 - shutdown only
                pass

    def inbound(self, message_id):
        row = self.state.execute(
            "SELECT payload, received_at, processed_at FROM inbound WHERE message_id=?",
            (message_id,),
        ).fetchone()
        if row is None:
            return None
        return {"payload": row[0], "received_at": row[1], "processed_at": row[2]}

    def main_run(self, message_id):
        row = self.sessions.execute(
            "SELECT status, result_json, error, updated_at FROM main_runs WHERE message_id=?",
            (message_id,),
        ).fetchone()
        if row is None:
            return None
        return {"status": row[0], "result_json": row[1], "error": row[2],
                "updated_at": row[3]}

    def outbox(self, message_id):
        row = self.state.execute(
            "SELECT peer_id, acked_at, attempts, last_error FROM outbox WHERE message_id=?",
            (message_id,),
        ).fetchone()
        if row is None:
            return None
        return {"peer_id": row[0], "acked_at": row[1], "attempts": row[2],
                "last_error": row[3]}

    def pending_inbound_ids(self):
        return [row[0] for row in self.state.execute(
            "SELECT message_id FROM inbound WHERE processed_at IS NULL")]

    def pending_main_ids(self):
        return [row[0] for row in self.sessions.execute(
            "SELECT message_id FROM main_runs WHERE status IN ('queued','running')")]

    def unacked_outbox_ids(self):
        return [row[0] for row in self.state.execute(
            "SELECT message_id FROM outbox WHERE acked_at IS NULL")]

    def pending_group_ids(self):
        return [row[0] for row in self.state.execute(
            "SELECT operation_id FROM group_outbox "
            "WHERE sent_at IS NULL AND cancelled_at IS NULL")]

    def active_children(self):
        rows = self.children.execute(
            "SELECT job_id, status, route FROM child_jobs "
            "WHERE status IN ('reserved','queued','running') "
            "OR (route='gpt_native' AND (status='interrupted' OR error='native stop unconfirmed' "
            "OR (status='completed' AND (result_json IS NULL OR result_json=''))))"
        ).fetchall()
        return [(row[0], row[1], row[2]) for row in rows]


def review_hashes(review):
    """Accept both reviewed schemas: explicit key or launch_once-style hashes."""
    hashes = review.get("hashes")
    if isinstance(hashes, dict) and hashes:
        return dict(hashes)
    resolved = {}
    program = review.get("program_sha256")
    if isinstance(program, str):
        resolved["participate.py"] = program
    elif isinstance(program, dict):
        for name in ("participate.py", "A_OFFLINE/participate.py"):
            if name in program:
                resolved["participate.py"] = program[name]
                break
    contract = review.get("contract_sha256")
    if isinstance(contract, str):
        resolved["contract.json"] = contract
    return resolved


def load_review():
    """Hash-check own script and the frozen contract against the review."""
    if not (OUT / "parent-review.json").is_file():
        raise Refused("REFUSED_REVIEW", "parent-review.json is missing in " + str(OUT))
    review = json.loads((OUT / "parent-review.json").read_text(encoding="utf-8"))
    if review.get('status') != 'PREPARATION_REVIEWED_NOT_ARMED':
        raise Refused('REFUSED_REVIEW', 'quality parent approval absent')
    if review.get("armed") is True:
        raise Refused("REFUSED_REVIEW", "review is armed; this participant is unarmed only")
    hashes = review_hashes(review)
    for required in ("participate.py", "contract.json"):
        if not is_hex64(hashes.get(required, "")):
            raise Refused("REFUSED_REVIEW", "no exact sha256 for " + required)
    for name, expected in hashes.items():
        if not is_hex64(expected):
            raise Refused("REFUSED_REVIEW", "invalid sha256 entry for " + str(name))
        candidate = OUT / name
        if not candidate.is_file():
            candidate = COHORT / name
        if not candidate.is_file():
            raise Refused("REFUSED_REVIEW", "reviewed file is missing: " + str(name))
        if sha256_file(candidate) != expected:
            raise Refused("REFUSED_REVIEW", "reviewed file changed: " + str(name))
    return review


def load_contract():
    """Validate the frozen contract against the fixed A_OFFLINE literals."""
    path = OUT / "contract.json"
    if not path.is_file():
        raise Refused("REFUSED_CONTRACT", "contract.json is missing in " + str(OUT))
    contract = json.loads(path.read_text(encoding="utf-8"))
    fixed = {
        "project_id": PROJECT, "task_id": TASK_ID, "task_version": 1,
        "work_id": WORK_ID, "phase": PHASE, "public_nonce": NONCE,
        "root_ready_message_id": GO_MESSAGE_ID,
        "authority_message_id": CONTRACT_MESSAGE_ID,
        "receipt_operation_id": RECEIPT_OP,
    }
    for key, value in fixed.items():
        if contract.get(key) != value:
            raise Refused("REFUSED_CONTRACT", "contract field mismatch: " + key)
    if not is_hex64(contract.get("authority_payload_sha256", "")):
        raise Refused("REFUSED_CONTRACT", "invalid authority_payload_sha256")
    maximum = contract.get("maximum_seconds")
    if type(maximum) is not int or not 0 < maximum <= MAX_SECONDS:
        raise Refused("REFUSED_CONTRACT", "maximum_seconds must be 1..600")
    sends = contract.get("sends")
    if not isinstance(sends, list) or len(sends) != 2:
        raise Refused("REFUSED_CONTRACT", "exactly two frozen sends required")
    expected_sends = (
        {"peer_id": "B", "task_id": COHORT_B_TASK, "task_version": 5,
         "operation_id": GO_TO_B_OP, "text": GO_TO_B_TEXT},
        {"peer_id": "B", "task_id": PROBE_TO_B_TASK, "task_version": 1,
         "operation_id": PROBE_TO_B_OP, "text": PROBE_TO_B_TEXT},
    )
    for frozen, expected in zip(sends, expected_sends):
        if not isinstance(frozen, dict):
            raise Refused("REFUSED_CONTRACT", "send entry is not an object")
        for key, value in expected.items():
            if frozen.get(key) != value:
                raise Refused("REFUSED_CONTRACT", "frozen send field mismatch: " + key)
    return contract


class HealthProbe:
    """Signed HMAC GET /v1/health without an HttpPeer instance; no secrets logged."""

    def __init__(self, url, secret):
        self.url = str(url).rstrip("/") + "/v1/health"
        self.secret = secret.encode("utf-8")

    def sample(self, expected_project):
        started = time.monotonic()
        outcome = {"result": "unreachable", "http_status": None,
                   "error_type": None, "node_id": None, "project_id": None}
        signature = hmac.new(self.secret, b"GET /v1/health",
                             hashlib.sha256).hexdigest()
        request = urllib.request.Request(
            self.url, method="GET", headers={"X-FPGA-Signature": signature},
        )
        try:
            with urllib.request.urlopen(request, timeout=PROBE_TIMEOUT_SECONDS) as response:
                status = int(response.status)
                body = response.read(4096)
            outcome["http_status"] = status
            if status != 200:
                outcome["result"] = "invalid"
                outcome["error_type"] = "HTTPStatus"
                return outcome, started, time.monotonic()
            try:
                data = json.loads(body.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                outcome["result"] = "invalid"
                outcome["error_type"] = "InvalidJSON"
                return outcome, started, time.monotonic()
            outcome["node_id"] = data.get("node_id") if isinstance(data, dict) else None
            outcome["project_id"] = (data.get("project_id")
                                     if isinstance(data, dict) else None)
            if (not isinstance(data, dict) or data.get("node_id") != "A"
                    or data.get("project_id") != expected_project):
                outcome["result"] = "invalid"
                outcome["error_type"] = "IdentityMismatch"
                return outcome, started, time.monotonic()
            outcome["result"] = "ok"
        except urllib.error.HTTPError as exc:
            outcome["http_status"] = int(exc.code)
            outcome["result"] = "invalid"
            outcome["error_type"] = "HTTPError"
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            outcome["result"] = "unreachable"
            outcome["error_type"] = type(exc).__name__
        except Exception as exc:  # noqa: BLE001 - any other answer is invalid
            outcome["result"] = "invalid"
            outcome["error_type"] = type(exc).__name__
        return outcome, started, time.monotonic()


class Participant:
    def __init__(self, mode):
        self.mode = mode
        self.mono_start = time.monotonic()
        self.bound = float(MAX_SECONDS)
        self.deadline = self.mono_start + self.bound
        self.contract = None
        self.control = None
        self.ledgers = None
        self.state_dir = None
        self.incomplete = []
        self.samples = 0
        self.ok_samples = 0
        self.unreachable_samples = 0
        self.max_streak = 0
        self.baseline = None
        self.last_good = None
        self.outage_streak = 0
        self.outage_confirmed = None
        self.post_completion_unreachable = False
        self.sends_blocked = False
        self.sent = {"go": False, "probe": False}
        self.authorized_outbox = set()
        self.send_records = {}
        self.b_seen = None
        self.b_complete = None
        self.b_ok = False
        self.b_evidence = None
        self.recovery = None
        self.guard_plan_sha256 = None
        self.go_payload_sha256 = None
        self.go_observed_sha256 = None
        self.stop_not_before = None
        self.restore_at = None
        self.local_health = None
        self.final_status = None

    # -- shared helpers ------------------------------------------------------

    def remaining(self):
        return self.deadline - time.monotonic()

    def require_budget(self, stage):
        if self.remaining() <= 0:
            raise BudgetExhausted(stage)

    def control_timeout(self, configured):
        """Per-I/O bound that can never outlive the whole-lifetime budget."""
        return max(0.5, min(float(configured), self.remaining()))

    def claim(self, name, payload):
        exclusive(OUT / name, payload)

    def add_incomplete(self, reason):
        if reason not in self.incomplete:
            self.incomplete.append(reason)

    def ensure_control(self):
        if self.control is None:
            self.control = LocalControlFileClient(discovery(ROOT))

    def log_event(self, event, **fields):
        append_jsonl(OUT / SAMPLES_LOG,
                     dict(kind=event, at_utc=utc_iso(),
                          mono=round(time.monotonic() - self.mono_start, 3),
                          **fields))

    def sample_counts(self):
        return {"total": self.samples, "ok": self.ok_samples,
                "unreachable": self.unreachable_samples,
                "max_unreachable_streak": self.max_streak}

    def monotonic_state(self):
        return {"start": round(self.mono_start, 3),
                "now": round(time.monotonic(), 3),
                "elapsed": round(time.monotonic() - self.mono_start, 3),
                "bound_seconds": self.bound}

    def artifact_hashes(self):
        artifacts = []
        for name in ARTIFACT_ORDER:
            path = OUT / name
            if path.is_file():
                artifacts.append({"path": str(path), "sha256": sha256_file(path)})
        return artifacts

    def idle_problems(self):
        problems = []
        for message_id in self.ledgers.pending_inbound_ids():
            problems.append("pending_inbound:" + str(message_id))
        for message_id in self.ledgers.pending_main_ids():
            problems.append("pending_main:" + str(message_id))
        for message_id in self.ledgers.unacked_outbox_ids():
            problems.append("unacked_outbox:" + str(message_id))
        for operation_id in self.ledgers.pending_group_ids():
            problems.append("pending_group:" + str(operation_id))
        for row in self.ledgers.active_children():
            problems.append("active_child:" + ":".join(str(item) for item in row))
        return problems

    def pending_problems(self, allowed_inbound):
        problems = []
        for message_id in self.ledgers.pending_inbound_ids():
            if message_id not in allowed_inbound:
                problems.append("inbound:" + str(message_id))
        for message_id in self.ledgers.pending_main_ids():
            if message_id not in allowed_inbound:
                problems.append("main:" + str(message_id))
        for message_id in self.ledgers.unacked_outbox_ids():
            if message_id not in self.authorized_outbox:
                problems.append("outbox:" + str(message_id))
        for row in self.ledgers.active_children():
            problems.append("child:" + ":".join(str(item) for item in row))
        return problems

    def wait_terminal_and_idle(self, message_id, stage):
        while True:
            self.require_budget(stage)
            inbound = self.ledgers.inbound(message_id)
            run = self.ledgers.main_run(message_id)
            complete = (inbound is not None and bool(inbound["processed_at"])
                        and run is not None and run["status"] == "completed"
                        and run["result_json"] is not None)
            if complete and not self.idle_problems():
                return run, inbound
            time.sleep(min(1.0, max(0.05, self.remaining() - 0.05)))

    def outbox_message_id(self, peer_id, operation_id):
        return peer_id + ":" + operation_id

    def write_failure(self, status, detail):
        value = {"mode": self.mode, "status": status, "detail": str(detail)[:300],
                 "at_utc": utc_iso(), "pid": os.getpid(),
                 "monotonic": self.monotonic_state(),
                 "incomplete_reasons": self.incomplete,
                 "NoARM": True, "NoStop": True, "service_mutations": 0}
        name = EXECUTE_FAILURE if self.mode == "execute" else PREPARE_FAILURE
        try:
            path = exclusive_final(OUT / name, value)
            self.final_status = status
            return path
        except Exception:  # noqa: BLE001 - failure reporting must never raise
            return None

    def write_timeout(self, stage):
        claims = {
            "execute": (OUT / EXECUTE_CLAIM).is_file(),
            "go_send": (OUT / GO_CLAIM).is_file(),
            "probe_send": (OUT / PROBE_CLAIM).is_file(),
            "collect_receipt": (OUT / RECEIPT_CLAIM).is_file(),
        }
        value = {"mode": "execute", "status": "TIMEOUT_NO_RECOVERY",
                 "stage": str(stage), "at_utc": utc_iso(),
                 "incomplete_reasons": self.incomplete,
                 "send_records": self.send_records, "claims": claims,
                 "baseline": self.baseline, "outage_confirmed": self.outage_confirmed,
                 "recovery": self.recovery, "b_to_c": self.b_evidence,
                 "samples": self.sample_counts(), "monotonic": self.monotonic_state(),
                 "note": ("No recovery within the local monotonic bound; no collect "
                          "claim and no new side effects."),
                 "NoARM": True, "NoStop": True, "service_mutations": 0}
        try:
            exclusive_final(OUT / EXECUTE_TIMEOUT, value)
        except Exception:  # noqa: BLE001
            pass
        self.final_status = "TIMEOUT_NO_RECOVERY"
        return 2

    def stdout_summary(self, code):
        return {"mode": self.mode, "status": self.final_status,
                "incomplete_reasons": self.incomplete, "exit_code": code,
                "artifacts": [item["path"] for item in self.artifact_hashes()]}

    # -- prepare -------------------------------------------------------------

    def run_prepare(self):
        load_review()
        self.contract = load_contract()
        mode_text = str(self.contract.get("mode", "")).upper()
        if "ARMED" in mode_text and "NOT_ARMED" not in mode_text:
            raise Refused("REFUSED_CONTRACT", "contract is not an unarmed prepare contract")
        self.bound = float(self.contract["maximum_seconds"])
        self.deadline = self.mono_start + self.bound
        self.state_dir = discovery(ROOT).parent
        self.ledgers = Ledgers(self.state_dir)
        self.ensure_control()
        self.claim(PREPARE_CLAIM, {
            "mode": "prepare", "at_utc": utc_iso(), "pid": os.getpid(),
            "program_sha256": sha256_file(OUT / "participate.py"),
            "contract_sha256": sha256_file(OUT / "contract.json"),
            "note": "durable at-most-once prepare admission; no replay"})
        capture = prepare_standby.capture()
        ready = {"mode": "prepare", "phase": PHASE, "nonce": NONCE,
                 "task_id": TASK_ID, "task_version": 1, "work_id": WORK_ID,
                 "at_utc": utc_iso(), "capture": capture,
                 "program_sha256": sha256_file(OUT / "participate.py"),
                 "contract_sha256": sha256_file(OUT / "contract.json"),
                 "NoARM": True, "NoStop": True, "service_mutations": 0,
                 "model_calls": 0}
        exclusive(OUT / PREPARE_READY, ready)
        self.log_event("prepare_ready", pid=os.getpid(),
                       prepare_ready_sha256=sha256_file(OUT / PREPARE_READY))
        run, inbound = self.wait_authority_terminal()
        active_children = self.wait_children_drain()
        if active_children:
            raise Refused('REFUSED_CHILDREN', 'children did not become terminal')
        load_review()
        if self.ledgers.outbox('A:' + ACCEPTED_OP) is not None:
            raise Refused('REFUSED_EXISTING_OPERATION', 'reuse original contract-accepted outbox; do not resend')
        accepted = {
            "at_utc": utc_iso(), "phase": PHASE, "nonce": NONCE,
            "work_id": WORK_ID, "task_id": TASK_ID, "task_version": 1,
            "operation_id": ACCEPTED_OP,
            "program_sha256": sha256_file(OUT / "participate.py"),
            "contract_sha256": sha256_file(OUT / "contract.json"),
            "parent_review_sha256": sha256_file(OUT / "parent-review.json"),
            "prepare_ready_sha256": sha256_file(OUT / PREPARE_READY),
            "pid": os.getpid(),
            "helper_process": capture.get("helper_process"),
            "job_isolation": capture.get("job_isolation"),
            "original_service": {key: capture.get(key) for key in
                                 ("task_root_pid", "supervisor_pid", "worker_pid", "task")},
            "parent_message_id": CONTRACT_MESSAGE_ID,
            "parent_completed": True,
            "parent_processed": True,
            "parent_processed_at": inbound["processed_at"],
            "parent_run": {"status": run["status"]},
            "quality_main": load_review().get('quality_main'),
            "selected_next_route": load_review().get('selected_next_route'),
            "children_active_after_wait": active_children,
            "interface": self.interface_description(),
            "NoARM": True, "NoStop": True, "service_mutations": 0,
            "task_registration": False, "model_calls": 0,
        }
        text = "CONTRACT_ACCEPTED " + compact(accepted)
        self.claim(ACCEPTED_CLAIM, {
            "purpose": "CONTRACT_ACCEPTED", "operation_id": ACCEPTED_OP,
            "text_sha256": sha256_hex(text.encode("utf-8")), "text": text,
            "at_utc": utc_iso(), "pid": os.getpid()})
        result = resident_call(self.control, "fpga_peer_send", {
            "peer_id": "A", "task_id": TASK_ID, "task_version": 1,
            "operation_id": ACCEPTED_OP, "text": text,
        }, self.control_timeout(CONTROL_TIMEOUT_SECONDS))
        outbox_id = self.outbox_message_id("A", ACCEPTED_OP)
        acked = None
        while self.remaining() > 0:
            row = self.ledgers.outbox(outbox_id)
            if row is not None and row["acked_at"]:
                acked = row
                break
            run_now = self.ledgers.main_run(CONTRACT_MESSAGE_ID)
            if run_now is None or run_now["status"] != "completed":
                raise Refused("REFUSED_AUTHORITY_REGRESSED",
                              "authority run left completed state during delivery wait")
            time.sleep(min(1.0, max(0.05, self.remaining() - 0.05)))
        delivery = {"mode": "prepare", "at_utc": utc_iso(),
                    "operation_id": ACCEPTED_OP, "message_id": outbox_id,
                    "resident_result": result, "outbox": acked
                    if acked is not None else self.ledgers.outbox(outbox_id),
                    "delivered": acked is not None,
                    "transport_terminal": acked is not None,
                    "parent_message_id": CONTRACT_MESSAGE_ID,
                    "parent_completed": True,
                    "parent_processed_at": inbound["processed_at"],
                    "NoARM": True, "NoStop": True, "service_mutations": 0}
        exclusive(OUT / PREPARE_DELIVERY, delivery)
        self.log_event("prepare_delivery", delivered=acked is not None,
                       operation_id=ACCEPTED_OP)
        if acked is None:
            self.final_status = "PREPARE_DELIVERY_NOT_ACKED"
            return 2
        self.final_status = "PREPARED_DELIVERED"
        return 0

    def wait_authority_terminal(self):
        while True:
            self.require_budget("wait_authority")
            inbound = self.ledgers.inbound(CONTRACT_MESSAGE_ID)
            if inbound is not None:
                envelope = json.loads(inbound["payload"])
                expected = {"message_id": CONTRACT_MESSAGE_ID, "project_id": PROJECT,
                            "sender": "A/Astra-A", "recipient": "C/Astra-C",
                            "task_id": TASK_ID, "task_version": 1,
                            "kind": "agent_report", "source": "astra"}
                for key, value in expected.items():
                    if envelope.get(key) != value:
                        raise Refused("REFUSED_AUTHORITY",
                                      "authority envelope field mismatch: " + key)
                observed = sha256_hex(inbound["payload"].encode("utf-8"))
                if observed != self.contract["authority_payload_sha256"]:
                    raise Refused("REFUSED_AUTHORITY",
                                  "authority payload sha256 differs from the contract")
                run = self.ledgers.main_run(CONTRACT_MESSAGE_ID)
                if (run is not None and run["status"] == "completed"
                        and run["result_json"] is not None
                        and inbound["processed_at"]):
                    return run, inbound
            time.sleep(min(1.0, max(0.05, self.remaining() - 0.05)))

    def wait_children_drain(self):
        while self.remaining() > 2.0:
            rows = self.ledgers.active_children()
            if not rows:
                return []
            time.sleep(min(1.0, max(0.05, self.remaining() - 0.05)))
        return [list(row) for row in self.ledgers.active_children()]

    def interface_description(self):
        return {
            "ordinary_scheduler_entrypoint": "A_OFFLINE/launch_once.py --execute --go-payload-sha256 <stored original inbound payload SHA256>",
            "go_setup_lead_seconds": 60,
            "go_setup_lead_note": "Root should announce STOP not earlier than 60 seconds after C GO dispatch, allowing parent terminal, Scheduler admission, Job proof and signed200 baseline; late baseline fails closed.",
            "program": "A_OFFLINE/participate.py",
            "modes": {"prepare": "--prepare",
                      "execute": ("--execute --go-payload-sha256 <64 lowercase hex "
                                  "of the stored raw UTF-8 GO payload>")},
            "expected_go_inbound": {
                "message_id": GO_MESSAGE_ID, "task_id": TASK_ID, "task_version": 1,
                "phase": PHASE, "nonce": NONCE, "operation_id": GO_OP,
                "text": "JSON object, optionally prefixed PARTICIPANT_GO followed by one space",
                "required_fields": ["phase", "nonce", "operation_id",
                                    "guard_plan_sha256", "stop_not_before_utc",
                                    "restore_at_utc"]},
            "planned_sends": [
                {"stage": "go", "peer_id": "B", "task_id": COHORT_B_TASK,
                 "task_version": 5, "operation_id": GO_TO_B_OP, "text": GO_TO_B_TEXT},
                {"stage": "probe", "peer_id": "B", "task_id": PROBE_TO_B_TASK,
                 "task_version": 1, "operation_id": PROBE_TO_B_OP,
                 "text": PROBE_TO_B_TEXT}],
            "expected_b_to_c_inbound": {
                "message_id": PROBE_INBOUND_ID, "task_id": PROBE_INBOUND_TASK,
                "task_version": 1, "from": "B/Astra-B", "text": PROBE_INBOUND_TEXT,
                "exact_ack": PROBE_ACK},
            "collect_operation_id": RECEIPT_OP,
            "bounds": {"maximum_seconds": MAX_SECONDS,
                       "sample_seconds": SAMPLE_SECONDS,
                       "unreachable_samples_required": UNREACHABLE_REQUIRED},
            "flags": {"arm": False, "standby": False, "task_registration": False,
                      "service_mutation": False, "model_calls": 0},
        }

    # -- execute -------------------------------------------------------------

    def run_execute(self, go_payload_sha256):
        load_review()
        self.contract = load_contract()
        self.bound = float(self.contract["maximum_seconds"])
        self.deadline = self.mono_start + self.bound
        if not is_hex64(go_payload_sha256 or ""):
            raise Refused("REFUSED_ARGS",
                          "--execute requires --go-payload-sha256 as 64 lowercase hex")
        self.go_payload_sha256 = go_payload_sha256
        self.state_dir = discovery(ROOT).parent
        self.ledgers = Ledgers(self.state_dir)
        inbound = self.ledgers.inbound(GO_MESSAGE_ID)
        if inbound is None:
            raise Refused("REFUSED_GO",
                          "participant-GO inbound is not stored: " + GO_MESSAGE_ID)
        self.go_observed_sha256 = sha256_hex(inbound["payload"].encode("utf-8"))
        if self.go_observed_sha256 != go_payload_sha256:
            raise Refused("REFUSED_GO",
                          "stored GO payload sha256 differs from --go-payload-sha256")
        envelope = json.loads(inbound["payload"])
        self.check_go_envelope(envelope)
        self.check_go_fields(self.parse_go_text(envelope))
        if any(self.ledgers.outbox(peer + ':' + op) is not None for peer, op in
               [('B', GO_TO_B_OP), ('B', PROBE_TO_B_OP), ('A', RECEIPT_OP)]):
            raise Refused('REFUSED_EXISTING_OPERATION', 'original A_OFFLINE outbox exists; inspect only')
        if self.ledgers.inbound(PROBE_INBOUND_ID) is not None:
            raise Refused('REFUSED_EXISTING_PROBE', 'B-to-C evidence predates this execution')
        self.ensure_control()
        self.claim(EXECUTE_CLAIM, {
            "mode": "execute", "at_utc": utc_iso(), "pid": os.getpid(),
            "go_payload_sha256": go_payload_sha256,
            "go_payload_observed_sha256": self.go_observed_sha256,
            "guard_plan_sha256": self.guard_plan_sha256,
            "program_sha256": sha256_file(OUT / "participate.py"),
            "contract_sha256": sha256_file(OUT / "contract.json"),
            "note": "durable at-most-once execution admission; no replay"})
        self.wait_terminal_and_idle(GO_MESSAGE_ID, "wait_go")
        capture = prepare_standby.capture()
        exclusive(OUT / EXECUTE_CAPTURE, {
            "mode": "execute", "at_utc": utc_iso(), "capture": capture})
        self.log_event("execute_capture", pid=os.getpid())
        self.check_local_health()
        probe = self.load_probe()
        self.log_event("measure_start", guard_plan_sha256=self.guard_plan_sha256,
                       stop_not_before_utc=self.stop_not_before.isoformat(),
                       restore_at_utc=self.restore_at.isoformat())
        outcome = self.measurement_loop(probe)
        if outcome != "recovery":
            return self.write_timeout("no_recovery")
        return self.finalize_recovery()

    def check_go_envelope(self, envelope):
        expected = {"message_id": GO_MESSAGE_ID, "project_id": PROJECT,
                    "sender": "A/Astra-A", "recipient": "C/Astra-C",
                    "task_id": TASK_ID, "task_version": 1,
                    "kind": "agent_report", "source": "astra"}
        for key, value in expected.items():
            if envelope.get(key) != value:
                raise Refused("REFUSED_GO", "GO envelope field mismatch: " + key)

    def parse_go_text(self, envelope):
        payload = envelope.get("payload")
        if not isinstance(payload, dict) or not isinstance(payload.get("text"), str):
            raise Refused("REFUSED_GO", "GO payload text is missing")
        body = payload["text"].strip()
        if body.startswith("PARTICIPANT_GO"):
            body = body[len("PARTICIPANT_GO"):].lstrip()
        try:
            data = json.loads(body)
        except ValueError:
            raise Refused("REFUSED_GO", "GO text is not valid JSON")
        if not isinstance(data, dict):
            raise Refused("REFUSED_GO", "GO text JSON is not an object")
        return data

    def check_go_fields(self, data):
        if data.get("phase") != PHASE:
            raise Refused("REFUSED_GO", "GO phase mismatch")
        if data.get("nonce") != NONCE:
            raise Refused("REFUSED_GO", "GO nonce mismatch")
        if data.get("operation_id") != GO_OP:
            raise Refused("REFUSED_GO", "GO operation_id mismatch")
        guard = data.get("guard_plan_sha256")
        if not is_hex64(guard):
            raise Refused("REFUSED_GO", "guard_plan_sha256 must be 64 lowercase hex")
        self.guard_plan_sha256 = guard
        try:
            stop = timestamp(data.get("stop_not_before_utc"))
            restore = timestamp(data.get("restore_at_utc"))
        except ValueError as exc:
            raise Refused("REFUSED_GO", "invalid UTC window: " + str(exc))
        if not stop < restore:
            raise Refused("REFUSED_GO_WINDOW",
                          "stop_not_before_utc must precede restore_at_utc")
        now = utc_now()
        if restore <= now:
            raise Refused("REFUSED_GO_WINDOW", "restore_at_utc is not in the future")
        if (restore - now).total_seconds() > self.bound:
            raise Refused("REFUSED_GO_WINDOW",
                          "restore_at_utc exceeds the bounded window")
        self.stop_not_before = stop
        self.restore_at = restore

    def check_local_health(self):
        health = resident_call(self.control, "health", {},
                               self.control_timeout(HEALTH_TIMEOUT_SECONDS))
        if not isinstance(health, dict):
            raise Refused("REFUSED_HEALTH", "local resident health is not an object")
        checks = {
            "started": health.get("started") is True,
            "node_id": health.get("node_id") == "C",
            "project_id": health.get("project_id") == PROJECT,
            "feishu_connected": health.get("feishu_connected") is True,
            "network_enabled": health.get("network_enabled") is True,
            "peer_error": health.get("peer_error") is None,
            "feishu_error": health.get("feishu_error") is None,
            "peer_listen_port": isinstance(health.get("peer_listen_port"), int)
            and health.get("peer_listen_port") > 0,
        }
        failed = [name for name, ok in checks.items() if not ok]
        if failed:
            raise Refused("REFUSED_HEALTH",
                          "local resident health invalid: " + ",".join(failed))
        self.local_health = {key: health.get(key) for key in (
            "node_id", "project_id", "mode", "started", "pid", "feishu_connected",
            "network_enabled", "peer_listen_port", "peer_error", "pending_inbound",
            "pending_outbox") if key in health}

    def load_probe(self):
        from fpga_mesh.runtime import NodeConfig
        config_path = self.state_dir.parents[1] / "node-c.toml"
        config = NodeConfig.load(config_path)
        if config.node_id != "C" or config.project_id != PROJECT:
            raise Refused("REFUSED_CONFIG", "local config identity mismatch")
        url = (config.peer_urls or {}).get("A")
        if not url:
            raise Refused("REFUSED_CONFIG", "no peer A URL in the local config")
        secret = os.environ.get(config.shared_secret_env, "").strip()
        if not secret and config.peer_shared_secret_file is not None:
            secret = Path(config.peer_shared_secret_file).read_text(
                encoding="utf-8-sig").strip()
        if not secret:
            raise Refused("REFUSED_CONFIG", "peer shared secret is not configured")
        return HealthProbe(url, secret)

    def sample(self, probe, role):
        outcome, started, ended = probe.sample(PROJECT)
        self.samples += 1
        entry = {"seq": self.samples, "kind": "sample", "role": role,
                 "at_utc": utc_iso(),
                 "mono_start": round(started, 3), "mono_end": round(ended, 3),
                 "mono_elapsed": round(ended - self.mono_start, 3),
                 "result": outcome["result"], "http_status": outcome["http_status"],
                 "error_type": outcome["error_type"], "node_id": outcome["node_id"],
                 "project_id": outcome["project_id"],
                 "baseline_present": self.baseline is not None,
                 "unreachable_streak": self.outage_streak,
                 "outage_confirmed": self.outage_confirmed is not None,
                 "b_to_c_complete": self.b_complete is not None}
        append_jsonl(OUT / SAMPLES_LOG, entry)
        return outcome, entry

    def on_ok(self, entry):
        self.ok_samples += 1
        if self.outage_confirmed is None:
            self.outage_streak = 0
        record = {"at_utc": entry["at_utc"], "mono": entry["mono_end"],
                  "node_id": entry["node_id"], "project_id": entry["project_id"]}
        self.last_good = record
        if self.baseline is None:
            self.baseline = record
            self.log_event("baseline", node_id=entry["node_id"],
                           project_id=entry["project_id"])
            return
        if self.outage_confirmed is None or self.recovery is not None:
            return
        self.recovery = {"at_utc": entry["at_utc"], "mono": entry["mono_end"]}
        self.sends_blocked = True
        if not (self.sent["go"] and self.sent["probe"]):
            self.add_incomplete("RECOVERY_BEFORE_BOTH_SENDS")
        elif self.b_complete is None:
            self.add_incomplete("A_ONLINE_BEFORE_B_TO_C_COMPLETE")
        elif not self.post_completion_unreachable:
            self.add_incomplete("NO_FRESH_OUTAGE_SAMPLE_AFTER_B_TO_C")
        self.log_event("a_restored", incomplete=list(self.incomplete))

    def on_unreachable(self, entry):
        self.unreachable_samples += 1
        if self.baseline is None:
            return
        if self.outage_confirmed is None:
            if utc_now() >= self.stop_not_before:
                self.outage_streak += 1
                self.max_streak = max(self.max_streak, self.outage_streak)
                if self.outage_streak >= UNREACHABLE_REQUIRED:
                    self.outage_confirmed = {"at_utc": entry["at_utc"],
                                             "mono": entry["mono_end"],
                                             "streak": self.outage_streak}
                    self.log_event("outage_confirmed", streak=self.outage_streak)
        elif self.b_complete is not None and not self.post_completion_unreachable:
            if utc_now() >= self.restore_at:
                self.add_incomplete('POST_COMPLETION_SAMPLE_OUTSIDE_ROOT_WINDOW')
                return
            self.post_completion_unreachable = True
            self.log_event("post_completion_unreachable_sample")

    def measurement_loop(self, probe):
        while True:
            if self.remaining() <= 0:
                return "timeout"
            outcome, entry = self.sample(probe, "sample")
            if outcome["result"] == "invalid":
                raise Refused(
                    "FAILED_CLOSED_HEALTH",
                    "invalid A health answer is not an outage: %s http=%s"
                    % (outcome["error_type"], outcome["http_status"]))
            if outcome["result"] == "ok":
                self.on_ok(entry)
            else:
                self.on_unreachable(entry)
            if self.recovery is not None:
                break
            if (self.outage_confirmed is not None and not self.sends_blocked
                    and not (self.sent["go"] and self.sent["probe"])):
                self.attempt_sends(probe)
            if self.sent["probe"]:
                self.check_b_to_c()
                self.monitor_while_waiting()
            wait = min(SAMPLE_SECONDS, max(0.05, self.remaining() - 0.05))
            if wait > 0:
                time.sleep(wait)
        return "recovery"

    def monitor_while_waiting(self):
        problems = self.pending_problems({PROBE_INBOUND_ID})
        for problem in problems[:5]:
            self.add_incomplete("UNAUTHORIZED_PENDING_DURING_WAIT:" + problem)

    def attempt_sends(self, probe):
        for stage, claim_name in (("go", GO_CLAIM), ("probe", PROBE_CLAIM)):
            if self.sent[stage]:
                continue
            if self.sends_blocked:
                return
            if self.remaining() <= 5.0:
                raise BudgetExhausted("send_" + stage)
            fresh, _ = self.sample(probe, "pre_send_" + stage)
            if fresh["result"] == "invalid":
                raise Refused(
                    "FAILED_CLOSED_HEALTH",
                    "invalid A health answer before %s send: %s"
                    % (stage, fresh["error_type"]))
            if fresh["result"] == "ok":
                self.add_incomplete("A_ONLINE_BEFORE_" + stage.upper() + "_SEND")
                self.sends_blocked = True
                return
            if utc_now() >= self.restore_at:
                self.add_incomplete("RESTORE_AT_REACHED_BEFORE_" + stage.upper() + "_SEND")
                self.sends_blocked = True
                return
            problems = self.pending_problems({PROBE_INBOUND_ID} if stage == 'probe' else set())
            for operation_id in self.ledgers.pending_group_ids():
                problems.append("group:" + str(operation_id))
            if problems:
                self.add_incomplete("UNAUTHORIZED_PENDING_BEFORE_" + stage.upper()
                                    + "_SEND:" + ";".join(problems[:3]))
                self.sends_blocked = True
                return
            load_review()
            if stage == "go":
                send = self.contract["sends"][0]
                self.authorized_outbox.add(self.outbox_message_id("B", GO_TO_B_OP))
            else:
                send = self.contract["sends"][1]
                self.authorized_outbox.add(self.outbox_message_id("B", PROBE_TO_B_OP))
            self.claim(claim_name, {
                "purpose": "GO_A_OFFLINE" if stage == "go" else "C_TO_B_PROBE",
                "peer_id": send["peer_id"], "task_id": send["task_id"],
                "task_version": send["task_version"],
                "operation_id": send["operation_id"],
                "text_sha256": sha256_hex(send["text"].encode("utf-8")),
                "at_utc": utc_iso(), "pid": os.getpid()})
            result = resident_call(self.control, "fpga_peer_send", {
                "peer_id": send["peer_id"], "task_id": send["task_id"],
                "task_version": int(send["task_version"]),
                "operation_id": send["operation_id"], "text": send["text"],
            }, self.control_timeout(CONTROL_TIMEOUT_SECONDS))
            self.send_records[stage] = {
                "operation_id": send["operation_id"],
                "message_id": self.outbox_message_id(send["peer_id"],
                                                     send["operation_id"]),
                "at_utc": utc_iso(),
                "mono": round(time.monotonic() - self.mono_start, 3),
                "resident_result": result}
            self.log_event("send_" + stage, operation_id=send["operation_id"],
                           result=result if isinstance(result, dict)
                           else str(type(result)))
            if not isinstance(result, dict) or result.get("duplicate") is True:
                self.add_incomplete("UNEXPECTED_DUPLICATE_" + stage.upper()
                                    + "_OPERATION")
                self.sends_blocked = True
                return
            self.sent[stage] = True

    def check_b_to_c(self):
        if self.b_complete is not None:
            return
        inbound = self.ledgers.inbound(PROBE_INBOUND_ID)
        if inbound is None:
            return
        if self.b_seen is None:
            self.b_seen = {"at_utc": utc_iso(),
                           "mono": round(time.monotonic() - self.mono_start, 3),
                           "received_at": inbound["received_at"],
                           "payload_sha256": sha256_hex(inbound["payload"].encode("utf-8"))}
            self.log_event("b_to_c_inbound_seen", message_id=PROBE_INBOUND_ID)
        run = self.ledgers.main_run(PROBE_INBOUND_ID)
        if run is None:
            return
        if run["status"] in ("failed", "interrupted"):
            self.add_incomplete("B_TO_C_RUN_" + run["status"].upper())
            self.finalize_b_evidence(inbound, run, ["run_" + run["status"]])
            return
        if (run["status"] != "completed" or run["result_json"] is None
                or not inbound["processed_at"]):
            return
        problems = self.b_to_c_checks(inbound, run)
        self.finalize_b_evidence(inbound, run, problems)

    def b_to_c_checks(self, inbound, run):
        problems = []
        if not self.stop_not_before <= utc_now() < self.restore_at:
            problems.append('completion_observed_outside_root_window')
        try:
            envelope = json.loads(inbound["payload"])
        except ValueError:
            return ["payload_not_json"]
        if not isinstance(envelope, dict):
            return ["payload_not_object"]
        expected = {"message_id": PROBE_INBOUND_ID, "project_id": PROJECT,
                    "sender": "B/Astra-B", "recipient": "C/Astra-C",
                    "task_id": PROBE_INBOUND_TASK, "task_version": 1,
                    "kind": "agent_report", "source": "astra"}
        for key, value in expected.items():
            if envelope.get(key) != value:
                problems.append("envelope_" + key)
        payload = envelope.get("payload")
        text = payload.get("text") if isinstance(payload, dict) else None
        if text != PROBE_INBOUND_TEXT:
            problems.append("inbound_text")
        try:
            result = json.loads(run["result_json"])
        except ValueError:
            return problems + ["result_not_json"]
        if not isinstance(result, dict):
            return problems + ["result_not_object"]
        turn = result.get("turn")
        if not isinstance(turn, dict) or turn.get("status") != "completed":
            problems.append("turn_not_completed")
        if not isinstance(turn, dict) or not turn.get('id') or not result.get('thread_id'):
            problems.append('turn_or_thread_id_missing')
        if result.get("text") != PROBE_ACK:
            problems.append("exact_ack")
        if not (isinstance(result.get("model"), str) and result["model"].strip()):
            problems.append("model_missing")
        if not (isinstance(result.get("reasoning_effort"), str)
                and result["reasoning_effort"].strip()):
            problems.append("effort_missing")
        if not (isinstance(result.get("provider"), str) and result["provider"].strip()):
            problems.append("provider_missing")
        elif result['provider'] != 'openai':
            problems.append('provider_not_official')
        return problems

    def finalize_b_evidence(self, inbound, run, problems):
        if self.b_complete is not None:
            return
        for problem in problems:
            self.add_incomplete("B_TO_C_" + str(problem).upper())
        if not problems:
            self.b_ok = True
        main_wait = None
        if run["status"] == "completed":
            try:
                waited = resident_call(self.control, "main_wait", {
                    "message_id": PROBE_INBOUND_ID,
                    "timeout_seconds": int(MAIN_WAIT_SECONDS)},
                    self.control_timeout(MAIN_WAIT_SECONDS + 10.0))
                result_text = None
                if isinstance(waited, dict):
                    inner = waited.get("result")
                    if isinstance(inner, dict):
                        result_text = inner.get("text")
                main_wait = {"at_utc": utc_iso(), "result_text": result_text}
                if result_text != PROBE_ACK:
                    self.add_incomplete("B_TO_C_MAIN_WAIT_DIVERGED")
            except Exception as exc:  # noqa: BLE001 - bounded observation only
                main_wait = {"at_utc": utc_iso(), "error_type": type(exc).__name__}
        result = None
        if run["result_json"]:
            try:
                result = json.loads(run["result_json"])
            except ValueError:
                result = None
        turn_status = None
        if isinstance(result, dict) and isinstance(result.get("turn"), dict):
            turn_status = result["turn"].get("status")
        evidence = {
            "message_id": PROBE_INBOUND_ID, "task_id": PROBE_INBOUND_TASK,
            "task_version": 1, "sender": "B/Astra-B", "source": "astra",
            "kind": "agent_report", "received_at": inbound["received_at"],
            "processed_at": inbound["processed_at"],
            "observed_at_utc": utc_iso(),
            "observed_mono": round(time.monotonic() - self.mono_start, 3),
            "payload_sha256": sha256_hex(inbound["payload"].encode("utf-8")),
            "expected_text": PROBE_INBOUND_TEXT, "exact_ack": PROBE_ACK,
            "main_run": {"status": run["status"], "updated_at": run["updated_at"],
                         "result_sha256": sha256_hex(run["result_json"].encode("utf-8"))
                         if run["result_json"] else None,
                         "text": result.get("text") if isinstance(result, dict) else None,
                         "turn_status": turn_status,
                         "model": result.get("model") if isinstance(result, dict) else None,
                         "reasoning_effort": result.get("reasoning_effort")
                         if isinstance(result, dict) else None,
                         "provider": result.get("provider")
                         if isinstance(result, dict) else None},
            "main_wait": main_wait,
            "original_inbound_payload": inbound['payload'],
            "original_main_result_json": run['result_json'],
            "turn_id": (result.get('turn') or {}).get('id') if isinstance(result, dict) else None,
            "thread_id": result.get('thread_id') if isinstance(result, dict) else None,
            "checks_ok": not problems, "problems": problems,
            "local_monotonic_bound_seconds": self.bound,
        }
        exclusive(OUT / B_EVIDENCE, evidence)
        self.b_evidence = evidence
        self.b_complete = {"at_utc": evidence["observed_at_utc"],
                           "mono": evidence["observed_mono"], "ok": self.b_ok,
                           "problems": list(problems)}
        self.log_event("b_to_c_complete", ok=self.b_ok, problems=problems)

    def missing_conditions(self):
        missing = []
        if self.baseline is None:
            missing.append("NO_VALID_SIGNED200_BASELINE")
        if self.outage_confirmed is None:
            missing.append("OUTAGE_NOT_CONFIRMED")
        if not (self.sent["go"] and self.sent["probe"]):
            missing.append("B_SENDS_NOT_BOTH_ISSUED")
        if not self.b_ok:
            missing.append("B_TO_C_EVIDENCE_NOT_OK")
        if not self.post_completion_unreachable:
            missing.append("NO_FRESH_UNREACHABLE_SAMPLE_AFTER_B_TO_C")
        return missing

    def build_receipt(self, status):
        return {
            "receipt": "A_OFFLINE_COLLECT_RECEIPT",
            "phase": PHASE, "nonce": NONCE, "operation_id": RECEIPT_OP,
            "task_id": TASK_ID, "task_version": 1, "work_id": WORK_ID,
            "status": status, "incomplete_reasons": list(self.incomplete),
            "guard_plan_sha256": self.guard_plan_sha256,
            "go_payload_sha256": self.go_payload_sha256,
            "go_payload_observed_sha256": self.go_observed_sha256,
            "stop_not_before_utc": self.stop_not_before.isoformat(),
            "restore_at_utc": self.restore_at.isoformat(),
            "baseline": self.baseline, "last_good": self.last_good,
            "outage_confirmed": self.outage_confirmed,
            "unreachable_samples_required": UNREACHABLE_REQUIRED,
            "post_completion_unreachable_sample": self.post_completion_unreachable,
            "samples": self.sample_counts(),
            "sends": self.send_records,
            "outbox": {
                "go": self.ledgers.outbox(self.outbox_message_id("B", GO_TO_B_OP)),
                "probe": self.ledgers.outbox(
                    self.outbox_message_id("B", PROBE_TO_B_OP))},
            "b_to_c": self.b_evidence,
            "recovery": self.recovery,
            "local_health": self.local_health,
            "local_monotonic": self.monotonic_state(),
            "program_sha256": sha256_file(OUT / "participate.py"),
            "contract_sha256": sha256_file(OUT / "contract.json"),
            "parent_review_sha256": sha256_file(OUT / "parent-review.json"),
            "artifacts": self.artifact_hashes(),
            "NoARM": True, "NoStop": True, "task_registration": False,
            "service_mutations": 0, "model_calls": 0,
            "at_utc": utc_iso(),
        }

    def finalize_recovery(self):
        receipt_allowed = self.remaining() >= RECEIPT_MIN_REMAINING_SECONDS
        if not receipt_allowed:
            self.add_incomplete("RECEIPT_SKIPPED_BOUND")
        for missing in self.missing_conditions():
            self.add_incomplete(missing)
        status = "CANDIDATE_MEASURED_OK" if not self.incomplete else "INCOMPLETE"
        receipt = self.build_receipt(status)
        sent_result = None
        if receipt_allowed:
            load_review()
            self.claim(RECEIPT_CLAIM, {
                "purpose": "COLLECT_RECEIPT", "operation_id": RECEIPT_OP,
                "text_sha256": sha256_hex(compact(receipt).encode("utf-8")),
                "receipt": receipt, "at_utc": utc_iso(), "pid": os.getpid(),
                "program_sha256": sha256_file(OUT / "participate.py")})
            try:
                sent_result = resident_call(self.control, "fpga_peer_send", {
                    "peer_id": "A", "task_id": TASK_ID, "task_version": 1,
                    "operation_id": RECEIPT_OP, "text": compact(receipt),
                }, self.control_timeout(CONTROL_TIMEOUT_SECONDS))
                exclusive(OUT / RECEIPT_DELIVERY, {
                    "mode": "execute", "at_utc": utc_iso(),
                    "operation_id": RECEIPT_OP,
                    "message_id": self.outbox_message_id("A", RECEIPT_OP),
                    "resident_result": sent_result,
                    "outbox": self.ledgers.outbox(
                        self.outbox_message_id("A", RECEIPT_OP))})
            finally:
                self.log_event("collect_receipt", resident_result=sent_result)
        outcome = {
            "mode": "execute", "status": status,
            "incomplete_reasons": list(self.incomplete),
            "receipt": {"sent": sent_result is not None,
                        "operation_id": RECEIPT_OP,
                        "receipt_sha256": sha256_hex(compact(receipt).encode("utf-8"))},
            "guard_plan_sha256": self.guard_plan_sha256,
            "go_payload_sha256": self.go_payload_sha256,
            "baseline": self.baseline, "last_good": self.last_good,
            "outage_confirmed": self.outage_confirmed,
            "post_completion_unreachable_sample": self.post_completion_unreachable,
            "recovery": self.recovery,
            "samples": self.sample_counts(),
            "sends": self.send_records,
            "b_to_c": self.b_evidence,
            "local_monotonic": self.monotonic_state(),
            "artifacts": self.artifact_hashes(),
            "NoARM": True, "NoStop": True, "task_registration": False,
            "service_mutations": 0, "model_calls": 0,
            "at_utc": utc_iso(),
        }
        exclusive_final(OUT / EXECUTE_OUTCOME, outcome)
        self.final_status = status
        return 0 if status == "CANDIDATE_MEASURED_OK" else 2


def parse_args(argv):
    parser = argparse.ArgumentParser(
        description="C A_OFFLINE participation runner (bounded, unarmed)")
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", action="store_true")
    modes.add_argument("--execute", action="store_true")
    parser.add_argument("--go-payload-sha256")
    args = parser.parse_args(argv)
    if args.prepare and args.go_payload_sha256 is not None:
        parser.error("--go-payload-sha256 is only valid with --execute")
    if args.execute and not is_hex64(args.go_payload_sha256 or ""):
        parser.error("--execute requires --go-payload-sha256 as 64 lowercase hex")
    return args


def entrypoint(argv=None):
    args = parse_args(argv)
    participant = Participant("prepare" if args.prepare else "execute")
    try:
        if args.prepare:
            code = participant.run_prepare()
        else:
            code = participant.run_execute(args.go_payload_sha256)
    except Refused as exc:
        participant.write_failure(exc.status, exc.detail)
        code = 2
    except BudgetExhausted as exc:
        if participant.mode == "execute":
            code = participant.write_timeout(exc.stage)
        else:
            participant.write_failure("TIMEOUT_" + exc.stage.upper(), str(exc))
            code = 2
    except Exception as exc:  # noqa: BLE001 - immutable failure, no autoretry
        participant.write_failure(
            "EXCEPTION", "%s: %s" % (type(exc).__name__, str(exc)[:250]))
        code = 2
    print(json.dumps(participant.stdout_summary(code), ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(entrypoint())
