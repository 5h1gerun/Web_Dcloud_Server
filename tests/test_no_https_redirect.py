from pathlib import Path

APP_PATH = Path(__file__).resolve().parents[1] / 'web' / 'app.py'


def test_no_https_redirect_middleware():
    text = APP_PATH.read_text(encoding='utf-8')
    assert 'https_redirect_mw' not in text
    assert 'FORCE_HTTPS' not in text
    assert 'HTTPPermanentRedirect' not in text
