from pathlib import Path

APP_PATH = Path(__file__).resolve().parents[1] / 'web' / 'app.py'


def test_cookie_domain_not_fixed():
    text = APP_PATH.read_text(encoding='utf-8')
    assert 'EncryptedCookieStorage(' in text
    # ドメインを固定しない設定になっていることを確認
    assert 'domain=None' in text
