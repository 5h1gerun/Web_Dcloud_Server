from pathlib import Path

LOGIN_HTML = Path(__file__).resolve().parents[1] / 'web' / 'templates' / 'login.html'
MOBILE_LOGIN_HTML = Path(__file__).resolve().parents[1] / 'web' / 'templates' / 'mobile' / 'login.html'


def test_login_requires_only_username():
    pc = LOGIN_HTML.read_text(encoding='utf-8')
    mobile = MOBILE_LOGIN_HTML.read_text(encoding='utf-8')
    assert 'name="password"' not in pc
    assert 'name="password"' not in mobile
