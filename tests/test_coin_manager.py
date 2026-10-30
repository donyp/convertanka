import server.coin_manager as cm


def test_calculate_cost():
    assert cm.calculate_cost(0) == 0
    assert cm.calculate_cost(-5) == 0
    assert cm.calculate_cost(1) == 1
    assert cm.calculate_cost(2) == 1
    assert cm.calculate_cost(3) == 2
    assert cm.calculate_cost(4) == 2
    assert cm.calculate_cost(5) == 3


def test_missing_file_returns_default(tmp_path, monkeypatch):
    monkeypatch.setattr(cm, "COINS_FILE", str(tmp_path / "missing.json"))
    assert cm.get_coin_data() == {"balance": 100}
    assert cm.get_balance() == 100


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(cm, "COINS_FILE", str(tmp_path / "coins.json"))
    cm.save_coin_data({"balance": 80})
    assert cm.get_coin_data() == {"balance": 80}
    assert cm.get_balance() == 80


def test_deduct_coins_success(tmp_path, monkeypatch):
    monkeypatch.setattr(cm, "COINS_FILE", str(tmp_path / "coins.json"))
    cm.save_coin_data({"balance": 100})
    ok, balance = cm.deduct_coins(30)
    assert ok is True
    assert balance == 70
    assert cm.get_balance() == 70


def test_deduct_coins_insufficient(tmp_path, monkeypatch):
    monkeypatch.setattr(cm, "COINS_FILE", str(tmp_path / "coins.json"))
    cm.save_coin_data({"balance": 20})
    ok, balance = cm.deduct_coins(50)
    assert ok is False
    assert balance == 20
    assert cm.get_balance() == 20


def test_corrupt_file_returns_default(tmp_path, monkeypatch):
    f = tmp_path / "coins.json"
    f.write_text("not valid json")
    monkeypatch.setattr(cm, "COINS_FILE", str(f))
    assert cm.get_coin_data() == {"balance": 100}


def test_balance_key_missing_defaults_to_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(cm, "COINS_FILE", str(tmp_path / "coins.json"))
    cm.save_coin_data({})
    assert cm.get_balance() == 0
