import pytest
from app.rag import (
    chunk_document_text,
    compute_dense_vector,
    cosine_similarity,
    index_attachment,
    delete_attachment_chunks,
    hybrid_search,
    format_rag_context,
)
from app.database import initialize, connect


@pytest.fixture(autouse=True)
def setup_db(tmp_path, monkeypatch):
    monkeypatch.setenv('APP_ENV', 'development')
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'chat.db'))
    initialize()


def test_chunking_preserves_page_numbers_and_metadata():
    text = (
        "--- [File: manual.pdf, Page 1] ---\nWelcome to the device manual.\n\n"
        "--- [File: manual.pdf, Page 2] ---\nThe emergency shutdown code is RED_ALERT_9999.\n\n"
        "--- [File: manual.pdf, Page 3] ---\nMaintenance instructions."
    )
    chunks = chunk_document_text(text, "manual.pdf")
    assert len(chunks) == 3
    assert chunks[1]['page_number'] == 2
    assert "RED_ALERT_9999" in chunks[1]['content']
    assert "manual.pdf, Page 2" in chunks[1]['section_title']


def test_dense_vector_embedding_and_cosine_similarity():
    v1 = compute_dense_vector("FastAPI and Python backend development")
    v2 = compute_dense_vector("FastAPI with Python web services")
    v3 = compute_dense_vector("Strawberry shortcake baking recipe")

    sim_related = cosine_similarity(v1, v2)
    sim_unrelated = cosine_similarity(v1, v3)

    assert sim_related > sim_unrelated
    assert sim_related > 0.25
    assert sim_unrelated < 0.15


def test_hybrid_search_rrf_retrieval():
    visitor = "v_rag_test"
    cid = "conv_123"
    aid = "att_456"

    # Setup parent records in db
    with connect() as db:
        db.execute(
            "INSERT INTO conversations(id, title, created_at, updated_at, visitor_id) VALUES (?, ?, ?, ?, ?)",
            (cid, "RAG Test Chat", "2026-10-08T00:00:00Z", "2026-10-08T00:00:00Z", visitor)
        )
        db.execute(
            '''
            INSERT INTO attachments(id, conversation_id, filename, content_type, size_bytes, file_path, created_at, extracted_text)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (aid, cid, "architecture.md", "text/markdown", 100, "/tmp/fake", "2026-10-08T00:00:00Z", "Sample")
        )

    doc_text = (
        "--- [File: architecture.md] ---\n"
        "Forma utilizes SQLite with Write-Ahead Logging (WAL) for persistent storage.\n"
        "Security is enforced through cryptographically signed HMAC visitor tokens.\n"
        "The model orchestration router automatically selects suitable models."
    )

    indexed_count = index_attachment(aid, cid, visitor, "architecture.md", doc_text)
    assert indexed_count >= 1

    # Search for WAL storage
    results = hybrid_search(visitor, "What storage engine and journal mode does Forma use?", conversation_id=cid)
    assert len(results) > 0
    top = results[0]
    assert "Write-Ahead Logging" in top['content'] or "SQLite" in top['content']
    assert top['filename'] == "architecture.md"
    assert 'rrf_score' in top

    # Format context
    formatted = format_rag_context(results, "storage engine")
    assert "<retrieved_evidence>" in formatted
    assert "</retrieved_evidence>" in formatted
    assert "architecture.md" in formatted
    assert "untrusted reference data" in formatted

    # Test deletion
    delete_attachment_chunks(aid)
    post_delete_results = hybrid_search(visitor, "storage engine", conversation_id=cid)
    assert len(post_delete_results) == 0
