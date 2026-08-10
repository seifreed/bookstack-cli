import pytest

from bookstack_cli.config import REQUIRED_SETTINGS, BookStackConfig, BookStackConfigError


def clear_bookstack_env(monkeypatch):
    for name in REQUIRED_SETTINGS:
        monkeypatch.delenv(name, raising=False)


def write_env(path, **values):
    path.write_text("\n".join(f"{key}={value}" for key, value in values.items()), encoding="utf-8")


def test_config_reads_dotenv(tmp_path, monkeypatch):
    clear_bookstack_env(monkeypatch)
    env_file = tmp_path / ".env"
    write_env(
        env_file,
        BOOKSTACK_URL="https://bookstack.test/",
        BOOKSTACK_TOKEN_ID="abc",
        BOOKSTACK_TOKEN_SECRET="secret",
    )

    config = BookStackConfig.from_env(env_file)

    assert config.url == "https://bookstack.test"
    assert config.authorization == "Token abc:secret"


def test_config_rejects_non_http_urls():
    with pytest.raises(BookStackConfigError):
        BookStackConfig("file:///tmp/bookstack", "abc", "secret")


def test_config_rejects_missing_values(tmp_path, monkeypatch):
    clear_bookstack_env(monkeypatch)

    with pytest.raises(BookStackConfigError, match="BOOKSTACK_URL, BOOKSTACK_TOKEN_ID, BOOKSTACK_TOKEN_SECRET"):
        BookStackConfig.from_env(tmp_path / "missing.env")


def test_dotenv_ignores_comments_blank_lines_and_invalid_lines(tmp_path, monkeypatch):
    clear_bookstack_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n# comment\nignored\nBOOKSTACK_URL='https://bookstack.test'\nBOOKSTACK_TOKEN_ID=\"abc\"\nBOOKSTACK_TOKEN_SECRET=secret\n",
        encoding="utf-8",
    )

    config = BookStackConfig.from_env(env_file)

    assert config.url == "https://bookstack.test"
    assert config.authorization == "Token abc:secret"


def test_dotenv_strips_utf8_bom(tmp_path, monkeypatch):
    clear_bookstack_env(monkeypatch)
    env_file = tmp_path / ".env"
    env_file.write_bytes(
        b"\xef\xbb\xbfBOOKSTACK_URL=https://bookstack.test\nBOOKSTACK_TOKEN_ID=abc\nBOOKSTACK_TOKEN_SECRET=secret\n"
    )

    config = BookStackConfig.from_env(env_file)

    assert config.url == "https://bookstack.test"
    assert config.authorization == "Token abc:secret"


def test_environment_overrides_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    write_env(
        env_file,
        BOOKSTACK_URL="https://wrong.test",
        BOOKSTACK_TOKEN_ID="wrong",
        BOOKSTACK_TOKEN_SECRET="wrong",
    )
    monkeypatch.setenv("BOOKSTACK_URL", "https://bookstack.test")
    monkeypatch.setenv("BOOKSTACK_TOKEN_ID", "abc")
    monkeypatch.setenv("BOOKSTACK_TOKEN_SECRET", "secret")

    config = BookStackConfig.from_env(env_file)

    assert config.url == "https://bookstack.test"
    assert config.authorization == "Token abc:secret"
