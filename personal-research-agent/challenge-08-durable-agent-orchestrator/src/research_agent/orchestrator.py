import hashlib
import json
import os
from pathlib import Path


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def tool_action(tool, **arguments):
    return {"kind": "tool", "tool": tool, "arguments": arguments, "answer": None}


def finish_action(answer):
    return {"kind": "finish", "tool": None, "arguments": {}, "answer": answer}


def budget(max_steps=8, max_tool_calls=6):
    if max_steps < 1 or max_tool_calls < 0:
        raise ValueError("invalid_budget")
    return {"max_steps": max_steps, "max_tool_calls": max_tool_calls}


def tool_spec(handler, required=(), optional=()):
    return {
        "handler": handler,
        "required": frozenset(required),
        "optional": frozenset(optional),
    }


def json_store(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    return {"root": root}


def journal_path(store, run_id):
    safe_name = hashlib.sha256(run_id.encode()).hexdigest() + ".json"
    return store["root"] / safe_name


def load_document(store, run_id):
    path = journal_path(store, run_id)
    if not path.exists():
        raise KeyError(run_id)
    return json.loads(path.read_text(encoding="utf-8"))


def save_document(store, run_id, document):
    path = journal_path(store, run_id)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(canonical(document), encoding="utf-8")
    os.replace(temporary, path)


def event_hash(previous_hash, kind, payload_json):
    material = f"{previous_hash}\n{kind}\n{payload_json}".encode()
    return hashlib.sha256(material).hexdigest()


def append_event(document, kind, payload):
    events = document["events"]
    previous_hash = "0" * 64 if not events else events[-1]["event_hash"]
    payload_json = canonical(payload)
    events.append({
        "sequence": len(events),
        "kind": kind,
        "payload_json": payload_json,
        "previous_hash": previous_hash,
        "event_hash": event_hash(previous_hash, kind, payload_json),
    })


def ensure_run(store, run_id, task):
    path = journal_path(store, run_id)
    if not path.exists():
        document = {
            "state": {
                "run_id": run_id,
                "task": task,
                "status": "running",
                "step": 0,
                "tool_calls": 0,
                "answer": None,
            },
            "calls": {},
            "events": [],
        }
        append_event(document, "run_started", {"task": task})
        save_document(store, run_id, document)
    else:
        document = load_document(store, run_id)
        if document["state"]["task"] != task:
            raise ValueError("run_id_task_mismatch")
    return snapshot(store, run_id)


def snapshot(store, run_id):
    return dict(load_document(store, run_id)["state"])


def validate_tool_action(action, tools):
    if action.get("kind") != "tool" or not action.get("tool") or action.get("answer") is not None:
        raise ValueError("invalid_tool_action")
    spec = tools.get(action["tool"])
    if spec is None:
        raise ValueError("unknown_tool")
    arguments = action.get("arguments")
    if not isinstance(arguments, dict):
        raise ValueError("invalid_arguments")
    keys = set(arguments)
    missing = spec["required"] - keys
    extra = keys - spec["required"] - spec["optional"]
    if missing:
        raise ValueError("missing_arguments:" + ",".join(sorted(missing)))
    if extra:
        raise ValueError("unknown_arguments:" + ",".join(sorted(extra)))
    return spec


def idempotency_key(run_id, step, action):
    material = {
        "run_id": run_id,
        "step": step,
        "tool": action["tool"],
        "arguments": action["arguments"],
    }
    return hashlib.sha256(canonical(material).encode()).hexdigest()


def begin_tool(store, run_id, key, step, action):
    document = load_document(store, run_id)
    existing = document["calls"].get(key)
    if existing is None:
        document["calls"][key] = {
            "run_id": run_id,
            "step": step,
            "tool": action["tool"],
            "arguments": action["arguments"],
            "status": "started",
            "result": None,
        }
        save_document(store, run_id, document)
        return "started"
    if existing["run_id"] != run_id or existing["step"] != step:
        raise ValueError("idempotency_key_collision")
    return existing["status"]


def completed_result(store, run_id, key):
    call_record = load_document(store, run_id)["calls"].get(key)
    if call_record is None or call_record["status"] != "completed":
        return None
    return call_record["result"]


def complete_tool(store, run_id, key, step, action, result):
    document = load_document(store, run_id)
    state = document["state"]
    call_record = document["calls"].get(key)
    if state["status"] != "running" or state["step"] != step or call_record is None:
        raise ValueError("stale_run_state")
    call_record["status"] = "completed"
    call_record["result"] = result
    state["step"] += 1
    state["tool_calls"] += 1
    append_event(document, "tool_completed", {
        "step": step,
        "tool": action["tool"],
        "arguments": action["arguments"],
        "result": result,
        "idempotency_key": key,
    })
    save_document(store, run_id, document)


def finish_run(store, run_id, step, answer):
    document = load_document(store, run_id)
    state = document["state"]
    if state["status"] != "running" or state["step"] != step:
        raise ValueError("stale_run_state")
    state["status"] = "completed"
    state["answer"] = answer
    state["step"] += 1
    append_event(document, "run_completed", {"step": step, "answer": answer})
    save_document(store, run_id, document)


def fail_run(store, run_id, reason):
    document = load_document(store, run_id)
    if document["state"]["status"] == "running":
        document["state"]["status"] = "failed"
        append_event(document, "run_failed", {"reason": reason})
        save_document(store, run_id, document)


def replay(store, run_id):
    previous_hash = "0" * 64
    state = {"status": None, "step": 0, "tool_calls": 0, "answer": None}
    for event in load_document(store, run_id)["events"]:
        expected = event_hash(previous_hash, event["kind"], event["payload_json"])
        if event["previous_hash"] != previous_hash or event["event_hash"] != expected:
            raise ValueError(f"trace_integrity_error:{event['sequence']}")
        payload = json.loads(event["payload_json"])
        if event["kind"] == "run_started":
            state.update(status="running", task=payload["task"])
        elif event["kind"] == "tool_completed":
            state["step"] += 1
            state["tool_calls"] += 1
        elif event["kind"] == "run_completed":
            state["step"] += 1
            state["status"] = "completed"
            state["answer"] = payload["answer"]
        elif event["kind"] == "run_failed":
            state["status"] = "failed"
        previous_hash = event["event_hash"]
    return state


def scripted_planner(actions):
    def choose_action(state):
        try:
            return actions[state["step"]]
        except IndexError as error:
            raise ValueError("planner_exhausted") from error
    return choose_action


def run_agent(
    store,
    tools,
    run_id,
    task,
    planner,
    limits=None,
    crash_hook=None,
):
    limits = limits or budget()
    crash_hook = crash_hook or (lambda stage: None)
    state = ensure_run(store, run_id, task)
    if state["status"] != "running":
        return state

    while True:
        state = snapshot(store, run_id)
        if state["step"] >= limits["max_steps"]:
            fail_run(store, run_id, "step_budget_exceeded")
            raise ValueError("step_budget_exceeded")

        action = planner(state)
        if action.get("kind") == "finish":
            if action.get("answer") is None or action.get("tool") is not None or action.get("arguments"):
                raise ValueError("invalid_finish_action")
            finish_run(store, run_id, state["step"], action["answer"])
            return snapshot(store, run_id)

        spec = validate_tool_action(action, tools)
        if state["tool_calls"] >= limits["max_tool_calls"]:
            fail_run(store, run_id, "tool_call_budget_exceeded")
            raise ValueError("tool_call_budget_exceeded")

        key = idempotency_key(run_id, state["step"], action)
        status = begin_tool(store, run_id, key, state["step"], action)
        if status == "completed":
            result = completed_result(store, run_id, key)
        else:
            result = spec["handler"](action["arguments"], key)
            crash_hook("after_tool")
        complete_tool(store, run_id, key, state["step"], action, result)
