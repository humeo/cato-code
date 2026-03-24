"""Tests for DB CRUD operations."""

from codebase_graph.storage.db import (
    delete_file_data,
    get_file_by_path,
    get_symbols_by_file,
    insert_edge,
    insert_symbol,
    open_db,
    resolve_edges,
    upsert_file,
)


def test_open_db_creates_project_database(tmp_path):
    conn = open_db(tmp_path)
    db_path = tmp_path / ".codebase-graph" / "index.db"
    try:
        row = conn.execute("PRAGMA journal_mode").fetchone()
        assert row[0].lower() == "wal"
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert {"files", "symbols", "edges"} <= tables
    finally:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()

    assert db_path.exists()


def test_upsert_file_insert(db):
    file_id = upsert_file(db, "src/main.py", "python", "abc123")
    assert file_id is not None
    row = get_file_by_path(db, "src/main.py")
    assert row["language"] == "python"
    assert row["content_hash"] == "abc123"


def test_upsert_file_update(db):
    file_id1 = upsert_file(db, "src/main.py", "python", "abc123")
    file_id2 = upsert_file(db, "src/main.py", "python", "def456")
    assert file_id1 == file_id2
    row = get_file_by_path(db, "src/main.py")
    assert row["content_hash"] == "def456"


def test_insert_symbol(db):
    file_id = upsert_file(db, "src/main.py", "python", "abc123")
    sym_id = insert_symbol(
        db,
        name="process",
        qualified_name="main.process",
        kind="function",
        file_id=file_id,
        line_start=10,
        line_end=25,
        signature="def process(data: list) -> dict",
    )
    assert sym_id is not None
    symbols = get_symbols_by_file(db, file_id)
    assert len(symbols) == 1
    assert symbols[0]["name"] == "process"


def test_insert_edge(db):
    file_id = upsert_file(db, "src/main.py", "python", "abc123")
    src_id = insert_symbol(
        db, "caller", "main.caller", "function", file_id, 1, 5, "def caller()"
    )
    insert_edge(
        db,
        source_id=src_id,
        target_name="callee",
        relation="calls",
        file_id=file_id,
        line=3,
    )
    row = db.execute("SELECT * FROM edges WHERE source_id = ?", (src_id,)).fetchone()
    assert row["target_name"] == "callee"
    assert row["target_id"] is None


def test_delete_file_data_removes_symbols_and_edges_for_file(db):
    file_id = upsert_file(db, "src/main.py", "python", "abc123")
    other_file_id = upsert_file(db, "src/lib.py", "python", "def456")
    src_id = insert_symbol(
        db, "caller", "main.caller", "function", file_id, 1, 5, "def caller()"
    )
    other_src_id = insert_symbol(
        db, "helper", "lib.helper", "function", other_file_id, 1, 2, "def helper()"
    )
    insert_edge(
        db,
        source_id=src_id,
        target_name="callee",
        relation="calls",
        file_id=file_id,
        line=3,
    )
    insert_edge(
        db,
        source_id=other_src_id,
        target_name="callee",
        relation="calls",
        file_id=other_file_id,
        line=2,
    )

    delete_file_data(db, file_id)

    assert get_symbols_by_file(db, file_id) == []
    assert db.execute("SELECT COUNT(*) FROM edges WHERE file_id = ?", (file_id,)).fetchone()[
        0
    ] == 0
    assert len(get_symbols_by_file(db, other_file_id)) == 1
    assert (
        db.execute(
            "SELECT COUNT(*) FROM edges WHERE file_id = ?", (other_file_id,)
        ).fetchone()[0]
        == 1
    )


def test_resolve_edges(db):
    file_id = upsert_file(db, "src/main.py", "python", "abc123")
    src_id = insert_symbol(
        db, "caller", "main.caller", "function", file_id, 1, 5, "def caller()"
    )
    tgt_id = insert_symbol(
        db, "callee", "main.callee", "function", file_id, 10, 20, "def callee()"
    )
    insert_edge(
        db,
        source_id=src_id,
        target_name="callee",
        relation="calls",
        file_id=file_id,
        line=3,
    )
    resolved = resolve_edges(db)
    assert resolved > 0
    row = db.execute(
        "SELECT target_id FROM edges WHERE source_id = ?", (src_id,)
    ).fetchone()
    assert row["target_id"] == tgt_id


def test_resolve_edges_leaves_ambiguous_duplicate_names_unresolved(db):
    file_id = upsert_file(db, "src/main.py", "python", "abc123")
    other_file_id = upsert_file(db, "src/lib.py", "python", "def456")
    src_id = insert_symbol(
        db, "caller", "main.caller", "function", file_id, 1, 5, "def caller()"
    )
    insert_symbol(
        db, "callee", "main.callee", "function", file_id, 10, 20, "def callee()"
    )
    insert_symbol(
        db, "callee", "lib.callee", "function", other_file_id, 1, 4, "def callee()"
    )
    insert_edge(
        db,
        source_id=src_id,
        target_name="callee",
        relation="calls",
        file_id=file_id,
        line=3,
    )

    resolved = resolve_edges(db)

    assert resolved == 0
    row = db.execute(
        "SELECT target_id FROM edges WHERE source_id = ?", (src_id,)
    ).fetchone()
    assert row["target_id"] is None
