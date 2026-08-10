from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

REQUIRED_SETTINGS = ("BOOKSTACK_URL", "BOOKSTACK_TOKEN_ID", "BOOKSTACK_TOKEN_SECRET")


class BookStackConfigError(ValueError):
    pass


@dataclass(frozen=True)
class BookStackConfig:
    url: str
    token_id: str
    token_secret: str

    def __post_init__(self) -> None:
        url = self.url.rstrip("/")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise BookStackConfigError("BOOKSTACK_URL must be an http(s) URL")
        object.__setattr__(self, "url", url)

    @classmethod
    def from_env(cls, env_file: str | os.PathLike[str] = ".env") -> BookStackConfig:
        values = _read_dotenv(Path(env_file)) | os.environ
        missing = [name for name in REQUIRED_SETTINGS if not values.get(name)]
        if missing:
            raise BookStackConfigError(f"Missing required setting(s): {', '.join(missing)}")
        return cls(
            url=values["BOOKSTACK_URL"],
            token_id=values["BOOKSTACK_TOKEN_ID"],
            token_secret=values["BOOKSTACK_TOKEN_SECRET"],
        )

    @property
    def authorization(self) -> str:
        return f"Token {self.token_id}:{self.token_secret}"


def _read_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values
