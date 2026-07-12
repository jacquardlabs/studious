"""Tests for bin/board-server — the stdlib-only HTTP+SSE reader over one
epic's .studious/epics/<slug>.json + <slug>.events.jsonl.

bin/board-server has no .py extension (it's an executable launch command, like
bin/gate-ledger), so it's loaded via importlib.machinery.SourceFileLoader below
rather than the tests/python/conftest.py sys.path convention used for scripts/.
"""
from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import socket
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_LOADER = importlib.machinery.SourceFileLoader("board_server", str(REPO / "bin" / "board-server"))
_SPEC = importlib.util.spec_from_loader("board_server", _LOADER)
board_server = importlib.util.module_from_spec(_SPEC)
sys.modules["board_server"] = board_server  # dataclass field introspection needs this registered first
_LOADER.exec_module(board_server)


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------

def test_slugify_matches_gate_ledger_shape() -> None:
    assert board_server.slugify("Checkout Revamp!!") == "checkout-revamp"
    assert board_server.slugify("  leading and trailing  ") == "leading-and-trailing"
    assert board_server.slugify("already-a-slug") == "already-a-slug"


# ---------------------------------------------------------------------------
# read_new_complete_lines — tolerant tailing of an append-only file
# ---------------------------------------------------------------------------

def test_read_new_complete_lines_returns_only_terminated_lines(tmp_path: Path) -> None:
    p = tmp_path / "events.jsonl"
    p.write_bytes(b'{"a":1}\n{"a":2}\n')
    lines, offset = board_server.read_new_complete_lines(p, 0)
    assert lines == [b'{"a":1}', b'{"a":2}']
    assert offset == p.stat().st_size


def test_read_new_complete_lines_defers_partial_trailing_line(tmp_path: Path) -> None:
    """Premortem item 1: a reader polling mid-append must not parse a truncated
    trailing line or drop it — it must be deferred to the next tick and then
    picked up complete once the writer finishes the line."""
    p = tmp_path / "events.jsonl"
    p.write_bytes(b'{"a":1}\n{"a":2,"partial')  # simulates an in-flight append

    lines, offset = board_server.read_new_complete_lines(p, 0)
    assert lines == [b'{"a":1}']
    assert offset == len(b'{"a":1}\n')  # the partial trailing line was NOT consumed

    # Writer finishes the line.
    with p.open("ab") as f:
        f.write(b'":true}\n')

    lines2, offset2 = board_server.read_new_complete_lines(p, offset)
    assert lines2 == [b'{"a":2,"partial":true}']
    assert offset2 == p.stat().st_size


def test_read_new_complete_lines_missing_file_is_empty(tmp_path: Path) -> None:
    lines, offset = board_server.read_new_complete_lines(tmp_path / "nope.jsonl", 0)
    assert lines == []
    assert offset == 0


def test_parse_event_lines_skips_malformed_without_raising(capsys) -> None:
    lines = [b'{"a":1}', b"not json at all", b'{"a":2}']
    events = board_server.parse_event_lines(lines)
    assert events == [{"a": 1}, {"a": 2}]
    assert "unparseable" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# build_schema
# ---------------------------------------------------------------------------

def test_build_schema_sorts_events_by_at_not_arrival_order() -> None:
    """Premortem item 2: events-format.md warns physical line order across
    concurrent writers can lag wall-clock `at` order — the served feed must
    be chronological regardless of the order lines were read in."""
    events = [
        {"at": "2026-07-11T14:19:41Z", "kind": "step"},
        {"at": "2026-07-11T14:02:03Z", "kind": "gate-verdict"},
        {"at": "2026-07-11T14:05:11Z", "kind": "story"},
    ]
    schema = board_server.build_schema({"slug": "x", "stories": {}}, events, "x")
    ats = [e["at"] for e in schema["events"]]
    assert ats == sorted(ats)


def test_build_schema_passes_vocabulary_verbatim() -> None:
    """gate-ledger's own status/verdict tokens must reach the schema unmodified
    — no web-layer renaming (reference/gate-vocabulary.md)."""
    blackboard = {
        "slug": "worker-evidence-and-board",
        "status": "running",
        "stories": {
            "board-events-log": {
                "status": "landed",
                "deps": [],
                "retries": {"audit": 1},
                "reason": "resolved: transient connection error, re-ran",
            }
        },
    }
    events = [{"at": "t", "kind": "gate-verdict", "gate": "audit", "verdict": "FIX AND RE-AUDIT"}]
    schema = board_server.build_schema(blackboard, events, "worker-evidence-and-board")
    assert schema["stories"]["board-events-log"]["status"] == "landed"
    assert schema["events"][0]["verdict"] == "FIX AND RE-AUDIT"


def test_build_schema_epic_object_is_a_field_subset_no_fabricated_nulls() -> None:
    blackboard = {"slug": "x", "status": "running", "stories": {}, "schemaVersion": 1}
    schema = board_server.build_schema(blackboard, [], "x")
    assert schema["epic"] == {"slug": "x", "status": "running"}
    assert "premortem" not in schema["epic"]  # absent field stays absent, never null
    assert "schemaVersion" not in schema["epic"]  # the blackboard's own version, not copied in


def test_build_schema_no_blackboard_yet_is_a_degenerate_200_shape() -> None:
    schema = board_server.build_schema(None, [], "never-ran")
    assert schema["epic"] == {"slug": "never-ran", "status": "unknown"}
    assert schema["stories"] == {}
    assert schema["events"] == []


# ---------------------------------------------------------------------------
# BoardState.poll — content-based change detection, not mtime-based
# ---------------------------------------------------------------------------

def _epics_dir(tmp_path: Path) -> Path:
    d = tmp_path / ".studious" / "epics"
    d.mkdir(parents=True)
    return d


def test_poll_detects_content_change_even_with_forced_identical_mtime(tmp_path: Path) -> None:
    """Premortem item 3: change detection must key on content, not mtime —
    a rewrite whose mtime lands in the same coarse granularity as the
    previous write must still be seen."""
    import os

    d = _epics_dir(tmp_path)
    bb = d / "epic.json"
    bb.write_text('{"slug":"epic","status":"running","stories":{}}')
    state = board_server.BoardState(epics_dir=d, epic_slug="epic")
    assert state.poll() is True  # first poll always "changes" (baseline)
    assert state.poll() is False  # nothing changed since

    bb.write_text('{"slug":"epic","status":"parked","stories":{}}')
    frozen = os.stat(bb).st_mtime
    os.utime(bb, (frozen, frozen))  # force an identical mtime despite different content
    assert state.poll() is True
    assert state.blackboard["status"] == "parked"


def test_poll_events_offset_advances_only_past_complete_lines(tmp_path: Path) -> None:
    d = _epics_dir(tmp_path)
    (d / "epic.json").write_text('{"slug":"epic","status":"running","stories":{}}')
    ev = d / "epic.events.jsonl"
    ev.write_bytes(b'{"at":"1","kind":"story","status":"pending"}\n')
    state = board_server.BoardState(epics_dir=d, epic_slug="epic")
    state.poll()
    assert len(state.events) == 1

    with ev.open("ab") as f:
        f.write(b'{"at":"2","kind":"story","status":"landed"')  # no trailing newline yet
    assert state.poll() is False  # blackboard unchanged, partial event line deferred
    assert len(state.events) == 1

    with ev.open("ab") as f:
        f.write(b'}\n')
    assert state.poll() is True
    assert len(state.events) == 2
    assert state.events[1]["status"] == "landed"


def test_poll_missing_epic_file_is_not_an_error(tmp_path: Path) -> None:
    d = _epics_dir(tmp_path)
    state = board_server.BoardState(epics_dir=d, epic_slug="never-ran")
    assert state.poll() is False  # digest None -> None, no change on first poll
    assert state.snapshot()["epic"]["status"] == "unknown"


# ---------------------------------------------------------------------------
# Integration: real HTTP + SSE server against a fixture epic
# ---------------------------------------------------------------------------

class _RunningServer:
    def __init__(self, tmp_path: Path, epic_slug: str, interval: float = 0.05) -> None:
        self.epics_dir = _epics_dir(tmp_path)
        self.epic_slug = epic_slug
        self.state = board_server.BoardState(epics_dir=self.epics_dir, epic_slug=epic_slug)
        self.state.poll()
        self.shutdown_event = threading.Event()
        self.httpd = board_server.BoardServer(
            ("127.0.0.1", 0), board_server.Handler, self.state, self.shutdown_event
        )
        self.port = self.httpd.server_address[1]
        self.interval = interval
        self._poll_thread = threading.Thread(
            target=board_server.poll_loop, args=(self.httpd, interval), daemon=True
        )
        self._accept_thread = threading.Thread(
            target=board_server.serve, args=(self.httpd,), daemon=True
        )

    def __enter__(self) -> "_RunningServer":
        self._poll_thread.start()
        self._accept_thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self.shutdown_event.set()
        self.httpd.server_close()
        self._accept_thread.join(timeout=2)
        self._poll_thread.join(timeout=2)

    def blackboard_path(self) -> Path:
        return self.epics_dir / f"{self.epic_slug}.json"

    def events_path(self) -> Path:
        return self.epics_dir / f"{self.epic_slug}.events.jsonl"


def _write_fixture_epic(server: _RunningServer, status: str = "running") -> None:
    server.blackboard_path().write_text(json.dumps({
        "schemaVersion": 1,
        "slug": server.epic_slug,
        "status": status,
        "stories": {
            "story-a": {"status": "landed", "deps": [], "retries": {}, "title": "Story A"},
        },
        "title": "Fixture epic",
        "goal": "prove the reader works",
    }))
    server.events_path().write_text(
        json.dumps({"at": "2026-07-11T10:00:00Z", "epic": server.epic_slug,
                    "story": "story-a", "kind": "story", "status": "landed"}) + "\n"
    )


def _http_get(port: int, path: str) -> tuple[int, dict]:
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_state_endpoint_returns_fixture_epic_shape(tmp_path: Path) -> None:
    with _RunningServer(tmp_path, "fixture-epic") as server:
        _write_fixture_epic(server)
        time.sleep(server.interval * 3)
        status, body = _http_get(server.port, "/state")
    assert status == 200
    assert body["epic"]["slug"] == "fixture-epic"
    assert body["epic"]["status"] == "running"
    assert body["stories"]["story-a"]["status"] == "landed"
    assert body["events"][0]["kind"] == "story"


def test_unknown_path_is_404(tmp_path: Path) -> None:
    with _RunningServer(tmp_path, "fixture-epic") as server:
        status, body = _http_get(server.port, "/nope")
    assert status == 404


# ---------------------------------------------------------------------------
# GET / — the Flight Deck page (board-ui story)
# ---------------------------------------------------------------------------

def _http_get_raw(port: int, path: str) -> tuple[int, str, str]:
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as resp:
            return resp.status, resp.headers.get("Content-Type", ""), resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", ""), e.read().decode("utf-8")


def test_root_serves_self_contained_html_page(tmp_path: Path) -> None:
    with _RunningServer(tmp_path, "fixture-epic") as server:
        status, content_type, body = _http_get_raw(server.port, "/")
    assert status == 200
    assert content_type.startswith("text/html")
    assert "<!doctype html>" in body.lower()
    # Self-contained: no <link>/<script src>/@import/<img src> pulling from
    # a network origin — this design's own bar (design doc, "Self-contained
    # and offline-correct"). The one legitimate "http://" substring in the
    # page is the SVG spec's own XML namespace URI passed to
    # createElementNS(), which browsers never dereference over the network
    # — excluded explicitly rather than banning "http://" outright.
    assert "<link" not in body
    assert "<script src=" not in body  # an actual src attribute, not this test's own prose
    assert "@import" not in body
    assert "<img" not in body
    non_svg_ns_urls = [
        line for line in body.splitlines()
        if ("http://" in line or "https://" in line) and "www.w3.org/2000/svg" not in line
    ]
    assert non_svg_ns_urls == []
    # The app.js placeholder was actually substituted, not left dangling.
    assert "__BOARD_UI_APP_JS__" not in body
    assert "computeGaugeOrder" in body  # a real function from app.js made it in


def test_root_route_does_not_change_state_or_events_behavior(tmp_path: Path) -> None:
    """Migration note in the design doc: /state and /events are unchanged
    by this route's addition."""
    with _RunningServer(tmp_path, "fixture-epic") as server:
        _write_fixture_epic(server)
        time.sleep(server.interval * 3)
        status, body = _http_get(server.port, "/state")
    assert status == 200
    assert body["stories"]["story-a"]["status"] == "landed"


def test_root_returns_500_not_a_crash_when_assets_are_broken(tmp_path: Path, monkeypatch) -> None:
    """A corrupted plugin install (missing placeholder, unreadable asset)
    fails this one request loudly rather than taking the whole server down
    — do_GET catches both OSError and render_page()'s own ValueError."""
    broken = tmp_path / "broken-assets"
    broken.mkdir()
    (broken / "index.html").write_text("<html><script></script></html>")  # no placeholder
    (broken / "app.js").write_text("// no-op")
    monkeypatch.setattr(board_server, "ASSETS_DIR", broken)
    with _RunningServer(tmp_path / "server", "fixture-epic") as server:
        status, _content_type, _body = _http_get_raw(server.port, "/")
        # The server itself is still alive and answering other routes.
        state_status, _ = _http_get(server.port, "/state")
    assert status == 500
    assert state_status == 200


def test_render_page_missing_placeholder_raises(tmp_path: Path, monkeypatch) -> None:
    """A page shell that lost its substitution marker fails loudly rather
    than silently shipping literal app.js source or an empty script body."""
    assets = tmp_path / "assets" / "board-ui"
    assets.mkdir(parents=True)
    (assets / "index.html").write_text("<html><script></script></html>")
    (assets / "app.js").write_text("// no-op")
    monkeypatch.setattr(board_server, "ASSETS_DIR", assets)
    try:
        board_server.render_page()
        raised = False
    except ValueError:
        raised = True
    assert raised


# ---------------------------------------------------------------------------
# maybe_open_browser — testable without ever launching a real browser
# ---------------------------------------------------------------------------

def test_maybe_open_browser_opens_when_requested() -> None:
    calls = []
    board_server.maybe_open_browser("http://127.0.0.1:1234", True, opener=calls.append)
    assert calls == ["http://127.0.0.1:1234"]


def test_maybe_open_browser_skips_when_not_requested() -> None:
    calls = []
    board_server.maybe_open_browser("http://127.0.0.1:1234", False, opener=calls.append)
    assert calls == []


def test_post_is_rejected_not_implemented(tmp_path: Path) -> None:
    import urllib.error
    import urllib.request

    with _RunningServer(tmp_path, "fixture-epic") as server:
        req = urllib.request.Request(f"http://127.0.0.1:{server.port}/state", method="POST")
        try:
            urllib.request.urlopen(req, timeout=5)
            raised = False
        except urllib.error.HTTPError as e:
            raised = True
            status = e.code
    assert raised
    assert status == 501  # http.server's default for a method this handler never implements


def _sse_read_frame(sock: socket.socket, leftover: bytes, timeout: float = 5.0) -> tuple[dict, bytes]:
    sock.settimeout(timeout)
    buf = leftover
    while b"\n\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            raise EOFError("SSE connection closed before a full frame arrived")
        buf += chunk
    frame, _, rest = buf.partition(b"\n\n")
    data_line = next(line for line in frame.decode().splitlines() if line.startswith("data: "))
    return json.loads(data_line[len("data: "):]), rest


def _sse_connect_after_headers(port: int) -> tuple[socket.socket, bytes]:
    """Open the SSE connection and consume exactly the HTTP header block.
    The server writes its initial event frame immediately after end_headers(),
    so a single recv() can return header bytes and body bytes together — any
    bytes read past the "\\r\\n\\r\\n" terminator are body and must be handed
    back to the caller, not discarded, or the first pushed frame is lost."""
    sock = socket.create_connection(("127.0.0.1", port), timeout=5)
    sock.sendall(f"GET /events HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\n\r\n".encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        buf += sock.recv(4096)
    _headers, _, leftover = buf.partition(b"\r\n\r\n")
    return sock, leftover


def test_sse_pushes_initial_snapshot_on_connect(tmp_path: Path) -> None:
    with _RunningServer(tmp_path, "fixture-epic") as server:
        _write_fixture_epic(server)
        time.sleep(server.interval * 3)
        sock, leftover = _sse_connect_after_headers(server.port)
        try:
            payload, _ = _sse_read_frame(sock, leftover)
        finally:
            sock.close()
    assert payload["epic"]["status"] == "running"


def test_sse_pushes_delta_within_one_tick_on_recorded_status_change(tmp_path: Path) -> None:
    """The acceptance criterion itself: a recorded status/verdict change pushes
    an SSE delta within one tick.

    The blackboard rewrite and the events.jsonl append below are two separate
    writes to two independently-polled files (BoardState.poll() ORs their two
    change signals). A poll tick can legitimately land between them, in which
    case poll() broadcasts an intermediate frame carrying only one side of the
    change — this is the documented eventually-consistent, self-heals-on-the-
    next-tick model (see poll()'s docstring), not a bug. Read frames until one
    converges on both writes rather than asserting on whichever frame happens
    to arrive first, or an intermediate frame makes this test flaky without
    the product being wrong."""
    with _RunningServer(tmp_path, "fixture-epic", interval=0.05) as server:
        _write_fixture_epic(server, status="running")
        time.sleep(server.interval * 3)
        sock, leftover = _sse_connect_after_headers(server.port)
        try:
            initial, rest = _sse_read_frame(sock, leftover)
            assert initial["epic"]["status"] == "running"

            # Simulate the writes gate-ledger's own epic-story-set/record verbs
            # would make: rewrite the blackboard and append one events.jsonl line.
            server.blackboard_path().write_text(json.dumps({
                "schemaVersion": 1, "slug": "fixture-epic", "status": "running",
                "stories": {"story-a": {"status": "audit", "deps": [], "retries": {"audit": 1},
                                          "reason": "kicked back", "title": "Story A"}},
                "title": "Fixture epic", "goal": "prove the reader works",
            }))
            with server.events_path().open("a") as f:
                f.write(json.dumps({"at": "2026-07-11T10:05:00Z", "epic": "fixture-epic",
                                     "story": "story-a", "kind": "gate-verdict",
                                     "gate": "audit", "verdict": "FIX AND RE-AUDIT"}) + "\n")

            pushed = None
            deadline = time.monotonic() + 5.0
            while pushed is None and time.monotonic() < deadline:
                frame, rest = _sse_read_frame(sock, rest, timeout=max(deadline - time.monotonic(), 0.1))
                story = frame["stories"].get("story-a", {})
                events = frame["events"]
                if (
                    story.get("status") == "audit"
                    and story.get("reason") == "kicked back"
                    and events
                    and events[-1].get("verdict") == "FIX AND RE-AUDIT"
                ):
                    pushed = frame
            assert pushed is not None, "no SSE frame converged on the recorded status+verdict within 5s"
        finally:
            sock.close()
    assert pushed["stories"]["story-a"]["status"] == "audit"
    assert pushed["stories"]["story-a"]["reason"] == "kicked back"
    assert pushed["events"][-1]["verdict"] == "FIX AND RE-AUDIT"


def test_two_server_instances_stay_isolated_to_their_own_epic(tmp_path: Path) -> None:
    """Premortem item 7: no shared global state — each launch is scoped to
    exactly its own epic slug's two files, even when two instances run at once."""
    tmp_a = tmp_path / "a"
    tmp_b = tmp_path / "b"
    tmp_a.mkdir()
    tmp_b.mkdir()
    with _RunningServer(tmp_a, "epic-a") as server_a, _RunningServer(tmp_b, "epic-b") as server_b:
        server_a.blackboard_path().write_text(json.dumps(
            {"schemaVersion": 1, "slug": "epic-a", "status": "running", "stories": {}}))
        server_b.blackboard_path().write_text(json.dumps(
            {"schemaVersion": 1, "slug": "epic-b", "status": "parked", "stories": {}}))
        time.sleep(max(server_a.interval, server_b.interval) * 3)
        _, body_a = _http_get(server_a.port, "/state")
        _, body_b = _http_get(server_b.port, "/state")
    assert body_a["epic"]["slug"] == "epic-a"
    assert body_a["epic"]["status"] == "running"
    assert body_b["epic"]["slug"] == "epic-b"
    assert body_b["epic"]["status"] == "parked"


# ---------------------------------------------------------------------------
# repo_root / epics_dir_for
# ---------------------------------------------------------------------------

def test_epics_dir_for_joins_studious_epics(tmp_path: Path) -> None:
    assert board_server.epics_dir_for(tmp_path) == tmp_path / ".studious" / "epics"


def test_epics_dir_for_none_root_is_cwd_relative() -> None:
    assert board_server.epics_dir_for(None) == Path(".studious/epics")


def test_repo_root_anchors_to_main_tree_from_a_linked_worktree(tmp_path: Path) -> None:
    """Mirrors bin/gate-ledger's own repo_root(): a linked worktree must
    resolve to the MAIN tree's root, not its own worktree directory, so
    board-server reads the one shared .studious/epics/ store."""
    import subprocess

    main_repo = tmp_path / "main"
    main_repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=main_repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=main_repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=main_repo, check=True)
    (main_repo / "f.txt").write_text("x")
    subprocess.run(["git", "add", "f.txt"], cwd=main_repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=main_repo, check=True)
    subprocess.run(["git", "branch", "story"], cwd=main_repo, check=True)

    worktree = tmp_path / "worktree"
    subprocess.run(["git", "worktree", "add", str(worktree), "story"], cwd=main_repo, check=True)

    assert board_server.repo_root(cwd=main_repo).resolve() == main_repo.resolve()
    assert board_server.repo_root(cwd=worktree).resolve() == main_repo.resolve()


def test_repo_root_outside_git_repo_is_none(tmp_path: Path) -> None:
    assert board_server.repo_root(cwd=tmp_path) is None
