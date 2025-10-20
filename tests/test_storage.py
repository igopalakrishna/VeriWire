from veriwire.storage import init_db, log_event, SessionLocal, Event


def test_log_event_creates_row():
    init_db()
    log_event("STREAM1", "test", "{}")
    with SessionLocal() as db:
        row = db.query(Event).order_by(Event.id.desc()).first()
        assert row is not None
        assert row.streamsid == "STREAM1"
        assert row.kind == "test"


