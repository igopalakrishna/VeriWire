from veriwire.bank_data import BankDB


def test_get_existing_payment():
    db = BankDB()
    p = db.get_payment("10SF917264")
    assert p is not None
    assert p.payee


def test_approve_then_conflict():
    db = BankDB()
    p = db.approve("10SF917264")
    assert p.status == "APPROVED"
    # approving again keeps status and does not error
    p2 = db.approve("10SF917264")
    assert p2.status == "APPROVED"


def test_cancel_then_conflict():
    db = BankDB()
    p = db.cancel("09NE482130")
    assert p.status == "CANCELED"
    # canceling again keeps status and does not error
    p2 = db.cancel("09NE482130")
    assert p2.status == "CANCELED"


