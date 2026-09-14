import json
import tempfile

from research_agent.orchestrator import (
    budget,
    finish_action,
    journal_path,
    json_store,
    load_document,
    replay,
    run_agent,
    scripted_planner,
    tool_action,
    tool_spec,
)


def expect_error(text, function):
    try:
        function()
    except Exception as error:
        assert text in str(error), (text, str(error))
    else:
        raise AssertionError(f"expected error containing {text}")


def make_search():
    state = {"results": {}, "effects": 0, "invocations": 0}

    def search(arguments, key):
        state["invocations"] += 1
        if key not in state["results"]:
            state["effects"] += 1
            state["results"][key] = {"items": [arguments["query"]]}
        return state["results"][key]

    return state, search


def make_agent(root):
    store = json_store(root)
    search_state, search = make_search()
    tools = {"search": tool_spec(search, required=("query",))}
    return store, search_state, tools


def test_completion_and_replay(root):
    store, search, tools = make_agent(root)
    plan = scripted_planner([
        tool_action("search", query="agent memory"),
        finish_action("Found one source."),
    ])
    result = run_agent(store, tools, "run-1", "research memory", plan)
    assert result["status"] == "completed"
    assert search["effects"] == 1
    rebuilt = replay(store, "run-1")
    assert {key: rebuilt[key] for key in ("status", "step", "tool_calls", "answer")} == {
        "status": "completed",
        "step": 2,
        "tool_calls": 1,
        "answer": "Found one source.",
    }


def test_idempotent_resume(root):
    crashed = {"value": False}

    def crash_once(stage):
        if stage == "after_tool" and not crashed["value"]:
            crashed["value"] = True
            raise RuntimeError("simulated_process_crash")

    store, search, tools = make_agent(root)
    plan = scripted_planner([
        tool_action("search", query="durable agents"),
        finish_action("Recovered."),
    ])
    expect_error(
        "simulated_process_crash",
        lambda: run_agent(store, tools, "run-2", "resume safely", plan, crash_hook=crash_once),
    )
    result = run_agent(store, tools, "run-2", "resume safely", plan)
    assert result["answer"] == "Recovered."
    assert search["invocations"] == 2
    assert search["effects"] == 1


def test_budgets(root):
    store, _, tools = make_agent(root)
    plan = scripted_planner([
        tool_action("search", query="one"),
        tool_action("search", query="two"),
        tool_action("search", query="three"),
    ])
    expect_error(
        "step_budget_exceeded",
        lambda: run_agent(
            store, tools, "run-3", "bounded loop", plan,
            limits=budget(max_steps=2, max_tool_calls=5),
        ),
    )
    assert load_document(store, "run-3")["state"]["status"] == "failed"

    store, _, tools = make_agent(root)
    expect_error(
        "tool_call_budget_exceeded",
        lambda: run_agent(
            store, tools, "run-4", "bounded tools", plan,
            limits=budget(max_steps=4, max_tool_calls=1),
        ),
    )
    assert replay(store, "run-4")["tool_calls"] == 1


def test_action_schemas(root):
    store, _, tools = make_agent(root)
    expect_error(
        "missing_arguments",
        lambda: run_agent(
            store, tools, "run-5", "bad schema",
            scripted_planner([tool_action("search")]),
        ),
    )
    store, _, tools = make_agent(root)
    expect_error(
        "unknown_arguments",
        lambda: run_agent(
            store, tools, "run-6", "bad schema",
            scripted_planner([tool_action("search", query="x", secret="no")]),
        ),
    )
    store, _, tools = make_agent(root)
    expect_error(
        "unknown_tool",
        lambda: run_agent(
            store, tools, "run-7", "bad tool",
            scripted_planner([tool_action("shell", command="rm")]),
        ),
    )


def test_tamper_detection(root):
    store, _, tools = make_agent(root)
    run_agent(
        store, tools, "run-8", "trace integrity",
        scripted_planner([finish_action("ok")]),
    )
    path = journal_path(store, "run-8")
    document = json.loads(path.read_text())
    document["events"][1]["payload_json"] = '{"answer":"tampered","step":0}'
    path.write_text(json.dumps(document))
    expect_error("trace_integrity_error:1", lambda: replay(store, "run-8"))


def main():
    tests = [
        test_completion_and_replay,
        test_idempotent_resume,
        test_budgets,
        test_action_schemas,
        test_tamper_detection,
    ]
    with tempfile.TemporaryDirectory() as root:
        for index, test in enumerate(tests):
            test(f"{root}/{index}")
            print(f"PASS {test.__name__}")
    print(f"{len(tests)} test groups passed")


if __name__ == "__main__":
    main()
