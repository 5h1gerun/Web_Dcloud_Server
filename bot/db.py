"""Async DB layer for Web_Discord_Server"""

from __future__ import annotations

# ── 標準ライブラリ ─────────────────────────
import asyncio, os, secrets, hashlib, sqlite3
import datetime as dt
from pathlib import Path
from typing import Any, List, Optional

# ── サードパーティ ────────────────────────
import aiosqlite
import scrypt  # pip install scrypt

# ── パス & 定数 ───────────────────────────
DB_PATH = Path(__file__).parents[1] / "data" / "web_discord_server.db"

SCRYPT_N, SCRYPT_r, SCRYPT_p = 2**15, 8, 1  # 32768:8:1
SCRYPT_BUFLEN = 64  # 512-bit

# ── スキーマ ──────────────────────────────
SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id  INTEGER UNIQUE,
    username    TEXT    UNIQUE NOT NULL,
    pw_hash     TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    gdrive_token TEXT,
    totp_secret  TEXT,
    totp_enabled INTEGER NOT NULL DEFAULT 0,
    totp_verified INTEGER NOT NULL DEFAULT 0,
    enc_key      TEXT
);
CREATE TABLE IF NOT EXISTS files (
    id              TEXT PRIMARY KEY,
    user_id         INTEGER NOT NULL,
    folder          TEXT    NOT NULL DEFAULT '',
    path            TEXT    NOT NULL,
    original_name   TEXT    NOT NULL,
    size            INTEGER NOT NULL,
    sha256          TEXT    NOT NULL,
    uploaded_at     TEXT    NOT NULL,
    expires_at      INTEGER NOT NULL DEFAULT 0,
    tags            TEXT    NOT NULL DEFAULT '',
    gdrive_id       TEXT,
    is_shared       INTEGER NOT NULL DEFAULT 0,
    token           TEXT,
    expiration_sec  INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS user_folders (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id   INTEGER NOT NULL,
    name      TEXT NOT NULL,
    parent_id INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY(parent_id) REFERENCES user_folders(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS shared_folders (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    channel_id INTEGER,
    webhook_url TEXT,
    parent_id INTEGER,
    FOREIGN KEY(parent_id) REFERENCES shared_folders(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS shared_folder_members (
    folder_id      INTEGER,
    discord_user_id INTEGER,
    PRIMARY KEY(folder_id, discord_user_id),
    FOREIGN KEY(folder_id) REFERENCES shared_folders(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS shared_files (
    id             TEXT PRIMARY KEY,
    folder_id      INTEGER NOT NULL,
    folder         TEXT NOT NULL DEFAULT '',
    file_name      TEXT NOT NULL,
    path           TEXT NOT NULL,
    size           INTEGER NOT NULL,
    is_shared      INTEGER NOT NULL,
    token          TEXT,
    uploaded_at    TEXT NOT NULL,
    expiration_sec INTEGER NOT NULL DEFAULT 0,
    expires_at     INTEGER NOT NULL DEFAULT 0,
    tags           TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(folder_id) REFERENCES shared_folders(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS send_logs (
    sender_discord_id INTEGER NOT NULL,
    target_discord_id INTEGER NOT NULL,
    file_id           TEXT    NOT NULL,
    sent_at           INTEGER NOT NULL,
    PRIMARY KEY(sender_discord_id, target_discord_id, file_id)
);
"""


# ── scrypt util ────────────────────────────
def scrypt_hash(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = scrypt.hash(
        password.encode(),
        salt,
        N=SCRYPT_N,
        r=SCRYPT_r,
        p=SCRYPT_p,
        buflen=SCRYPT_BUFLEN,
    )
    return f"{SCRYPT_N}:{SCRYPT_r}:{SCRYPT_p}${salt.hex()}${dk.hex()}"


def verify_password(password: str, hashed: str) -> bool:
    try:
        params, salt_hex, dk_hex = hashed.split("$")
        n, r, p = map(int, params.split(":"))
        salt, dk_exp = bytes.fromhex(salt_hex), bytes.fromhex(dk_hex)
        dk_act = scrypt.hash(password.encode(), salt, N=n, r=r, p=p, buflen=len(dk_exp))
        return secrets.compare_digest(dk_act, dk_exp)
    except Exception:
        return False


# ── DB 初期化 ──────────────────────────────
async def init_db(db_path: Path = DB_PATH) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA)
        cur = await db.execute("PRAGMA table_info(files)")
        info = await cur.fetchall()
        cols = {row[1] for row in info}
        id_type = next((row[2] for row in info if row[1] == "id"), "").upper()
        if id_type and id_type != "TEXT":
            await db.execute("ALTER TABLE files RENAME TO files_old")
            await db.execute(
                """
                CREATE TABLE files (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    folder TEXT NOT NULL DEFAULT '',
                    path TEXT NOT NULL,
                    original_name TEXT NOT NULL,
                    size INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    uploaded_at TEXT NOT NULL,
                    expires_at INTEGER NOT NULL DEFAULT 0,
                    tags TEXT NOT NULL DEFAULT '',
                    gdrive_id TEXT,
                    is_shared INTEGER NOT NULL DEFAULT 0,
                    token TEXT,
                    expiration_sec INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
            await db.execute(
                """
                INSERT INTO files (
                    id, user_id, folder, path, original_name, size, sha256,
                    uploaded_at, expires_at, tags, gdrive_id, is_shared, token,
                    expiration_sec
                )
                SELECT
                    id, user_id, folder, path, original_name, size, sha256,
                    uploaded_at, expires_at, tags, gdrive_id, is_shared, token,
                    expiration_sec
                FROM files_old
                """
            )
            await db.execute("DROP TABLE files_old")
        if "gdrive_id" not in cols:
            await db.execute("ALTER TABLE files ADD COLUMN gdrive_id TEXT")
        if "is_shared" not in cols:
            await db.execute(
                "ALTER TABLE files ADD COLUMN is_shared INTEGER NOT NULL DEFAULT 0"
            )
        if "token" not in cols:
            await db.execute("ALTER TABLE files ADD COLUMN token TEXT")
        if "expiration_sec" not in cols:
            await db.execute(
                "ALTER TABLE files ADD COLUMN expiration_sec INTEGER NOT NULL DEFAULT 0"
            )
        cur = await db.execute("PRAGMA table_info(users)")
        ucols = {row[1] for row in await cur.fetchall()}
        if "gdrive_token" not in ucols:
            await db.execute("ALTER TABLE users ADD COLUMN gdrive_token TEXT")
        if "totp_secret" not in ucols:
            await db.execute("ALTER TABLE users ADD COLUMN totp_secret TEXT")
        if "totp_enabled" not in ucols:
            await db.execute(
                "ALTER TABLE users ADD COLUMN totp_enabled INTEGER NOT NULL DEFAULT 0"
            )
        if "totp_verified" not in ucols:
            await db.execute(
                "ALTER TABLE users ADD COLUMN totp_verified INTEGER NOT NULL DEFAULT 0"
            )
        if "enc_key" not in ucols:
            await db.execute("ALTER TABLE users ADD COLUMN enc_key TEXT")
        await db.commit()


# ───────────────────────────────────────────
# Database クラス
# ───────────────────────────────────────────
class Database:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.conn: aiosqlite.Connection | None = None

    async def connect(self):
        self.conn = await aiosqlite.connect(self.db_path)

    async def close(self):
        if self.conn:
            await self.conn.close()
            self.conn = None

    async def verify_user(self, username: str, password: str) -> bool:
        """
        users テーブルから pw_hash を取り出し、
        平文 password を scrypt で検証して一致すれば True を返す。
        """
        # 1. ハッシュを取得
        row = await self.fetchone(
            "SELECT pw_hash FROM users WHERE username = ?", username
        )
        if not row:
            return False

        # 2. verify_password ヘルパーでチェック
        #    verify_password(password: str, hashed: str) -> bool
        return verify_password(password, row["pw_hash"])

    async def get_user_pk(self, discord_id: int) -> Optional[int]:
        """Discord ユーザID から users.id（PK）を返す"""
        row = await self.fetchone("SELECT id FROM users WHERE discord_id=?", discord_id)
        return row["id"] if row else None

    async def get_gdrive_token(self, user_id: int) -> Optional[str]:
        row = await self.fetchone(
            "SELECT gdrive_token FROM users WHERE id=?",
            user_id,
        )
        return row["gdrive_token"] if row and row["gdrive_token"] else None

    async def set_gdrive_token(self, user_id: int, token: Optional[str]) -> None:
        await self.execute(
            "UPDATE users SET gdrive_token=? WHERE id=?",
            token,
            user_id,
        )

    async def set_shared(self, file_id: str, shared: bool):
        """指定ファイルの共有フラグを更新"""
        val = 1 if shared else 0
        await self.execute("UPDATE files SET is_shared=? WHERE id=?", val, file_id)

    async def open(self):
        """Bot 常駐用：非コンテキストで接続を確立する"""
        if self.conn:  # すでに開いていれば何もしない
            return
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row

    async def create_user_folder(
        self, user_id: int, name: str, parent_id: Optional[int] = None
    ) -> int:
        cur = await self.conn.execute(
            "INSERT INTO user_folders (user_id, name, parent_id) VALUES (?, ?, ?)",
            (user_id, name, parent_id),
        )
        await self.conn.commit()
        return cur.lastrowid

    async def create_shared_folder(
        self, folder_name: str, channel_id: int, webhook_url: str = ""
    ) -> int:
        """
        shared_folders テーブルに name, channel_id, webhook_url を INSERT する。
        """
        cursor = await self.conn.execute(
            "INSERT INTO shared_folders (name, channel_id, webhook_url) VALUES (?, ?, ?)",
            (folder_name, channel_id, webhook_url),
        )
        await self.conn.commit()
        return cursor.lastrowid

    async def set_folder_channel(self, folder_id: int, channel_id: int) -> None:
        await self.conn.execute(
            "UPDATE shared_folders SET channel_id = ? WHERE id = ?",
            (channel_id, folder_id),
        )
        await self.conn.commit()

    async def set_folder_webhook(self, folder_id: int, webhook_url: str) -> None:
        await self.conn.execute(
            "UPDATE shared_folders SET webhook_url = ? WHERE id = ?",
            (webhook_url, folder_id),
        )
        await self.conn.commit()

    async def add_shared_folder_member(
        self, folder_id: int, discord_user_id: int
    ) -> None:
        await self.conn.execute(
            """
            INSERT OR IGNORE INTO shared_folder_members
                (folder_id, discord_user_id)
            VALUES (?, ?)
            """,
            (folder_id, discord_user_id),
        )
        await self.conn.commit()

    async def get_shared_folder(self, folder_id: int) -> sqlite3.Row | None:
        """
        shared_folders テーブルからレコードを取得
        """
        cursor = await self.conn.execute(
            "SELECT id, name, channel_id, webhook_url FROM shared_folders WHERE id = ?",
            (folder_id,),
        )
        return await cursor.fetchone()

    async def delete_shared_folder(self, folder_id: int) -> None:
        """
        shared_folders と folder_members を削除
        FOREIGN KEY ... ON DELETE CASCADE が効いていれば
        shared_folder_members は自動で消えます。
        """
        await self.conn.execute(
            "DELETE FROM shared_folders WHERE id = ?",
            (folder_id,),
        )
        await self.conn.commit()  # ← ここでコミット

    async def delete_shared_folder_member(
        self, folder_id: int, discord_user_id: int
    ) -> None:
        """
        shared_folder_members テーブルから
        (folder_id, discord_user_id) のレコードを削除
        """
        await self.conn.execute(
            "DELETE FROM shared_folder_members WHERE folder_id = ? AND discord_user_id = ?",
            (folder_id, discord_user_id),
        )
        await self.conn.commit()

    async def get_shared_folder_by_channel(self, channel_id: int) -> sqlite3.Row | None:
        """
        channel_id から shared_folders レコードを取得。
        """
        cursor = await self.conn.execute(
            "SELECT id, name, webhook_url FROM shared_folders WHERE channel_id = ?",
            (channel_id,),
        )
        return await cursor.fetchone()

    async def add_shared_file(
        self, file_id: str, folder_id: int, filename: str, path: str, tags: str = ""
    ) -> None:
        """shared_files テーブルにレコードを追加"""
        await self.conn.execute(
            "INSERT INTO shared_files "
            "  (id, folder_id, file_name, path, size, is_shared, token, uploaded_at, expires_at, tags) "
            "VALUES (?, ?, ?, ?, ?, 1, NULL, strftime('%s','now'), 0, ?)",
            (file_id, folder_id, filename, path, os.path.getsize(path), tags),
        )
        await self.conn.commit()

    async def get_shared_file(self, file_id: str) -> Optional[aiosqlite.Row]:
        """shared_files から単一レコードを取得"""
        return await self.fetchone("SELECT * FROM shared_files WHERE id = ?", file_id)

    async def set_shared_file_shared(self, file_id: str, shared: bool):
        """shared_files テーブルの is_shared を更新"""
        val = 1 if shared else 0
        await self.execute(
            "UPDATE shared_files SET is_shared = ?, share_token = ? WHERE id = ?",
            val,
            shared
            and None
            or None,  # share_token は HMAC で都度生成する場合は NULL、DBに保持しない
            file_id,
        )

    # --- context manager ---
    async def __aenter__(self):  # type: ignore[override]
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        return self

    async def __aexit__(self, *_):  # type: ignore[override]
        await self.conn.close()

    async def commit(self):
        """明示コミット用"""
        if self.conn:
            await self.conn.commit()

    # --- generic helpers ---
    async def execute(self, sql: str, *params: Any):
        await self.conn.execute(sql, params)
        await self.conn.commit()

    async def fetchone(self, sql: str, *params: Any):
        cur = await self.conn.execute(sql, params)
        row = await cur.fetchone()
        await cur.close()
        return row

    async def fetchall(self, sql: str, *params: Any):
        cur = await self.conn.execute(sql, params)
        rows = await cur.fetchall()
        await cur.close()
        return rows

    # ========== domain-specific ==========

    # ユーザ
    async def add_user(self, discord_id: int, username: str, password: str):
        await self.execute(
            "INSERT OR REPLACE INTO users(discord_id, username, pw_hash, created_at) VALUES (?,?,?,?)",
            discord_id,
            username,
            scrypt_hash(password),
            dt.datetime.utcnow().isoformat(),
        )

    async def user_exists(self, discord_id: int) -> bool:
        row = await self.fetchone("SELECT 1 FROM users WHERE discord_id=?", discord_id)
        return bool(row)

    async def list_users(self):
        """Return all users ordered by username."""
        return await self.fetchall(
            "SELECT discord_id, username FROM users ORDER BY username"
        )

    async def get_user_folder(self, folder_id: int) -> Optional[aiosqlite.Row]:
        return await self.fetchone(
            "SELECT id, name, parent_id FROM user_folders WHERE id=?",
            folder_id,
        )

    async def list_user_folders(self, user_id: int, parent_id: Optional[int] = None):
        if parent_id is None:
            return await self.fetchall(
                "SELECT id, name FROM user_folders WHERE user_id=? AND parent_id IS NULL ORDER BY name",
                user_id,
            )
        return await self.fetchall(
            "SELECT id, name FROM user_folders WHERE user_id=? AND parent_id=? ORDER BY name",
            user_id,
            parent_id,
        )

    async def delete_user_folder(self, folder_id: int) -> None:
        rows = await self.fetchall(
            "SELECT id FROM user_folders WHERE parent_id=?",
            folder_id,
        )
        for r in rows:
            await self.delete_user_folder(r["id"])
        frows = await self.fetchall(
            "SELECT path FROM files WHERE folder=?",
            str(folder_id),
        )
        for fr in frows:
            try:
                Path(fr["path"]).unlink(missing_ok=True)
            except Exception:
                pass
        await self.execute("DELETE FROM files WHERE folder=?", str(folder_id))
        await self.execute("DELETE FROM user_folders WHERE id=?", folder_id)

    async def delete_all_subfolders(
        self, user_id: int, parent_id: Optional[int] = None
    ) -> None:
        rows = await self.list_user_folders(user_id, parent_id)
        for r in rows:
            await self.delete_user_folder(r["id"])

    # ファイル
    async def add_file(
        self,
        file_id: str,
        user_id: int,
        folder: str,
        original_name: str,
        path: str,
        size: int,
        sha256: str,
        tags: str = "",
        gdrive_id: str | None = None,
    ):
        await self.conn.execute(
            """INSERT INTO files
            (id, user_id, folder, path, original_name, size, sha256, uploaded_at,
             expires_at, tags, gdrive_id, is_shared, token, expiration_sec)
            VALUES (?, ?, ?, ?, ?, ?, ?, strftime('%s','now'), 0, ?, ?, 0, NULL, 0)""",
            (
                file_id,
                user_id,
                folder,
                path,
                original_name,
                size,
                sha256,
                tags,
                gdrive_id,
            ),
        )
        await self.conn.commit()

    async def list_files(self, user_id: int, folder: str = ""):
        return await self.fetchall(
            "SELECT id, original_name, size, uploaded_at, tags "
            "FROM   files "
            "WHERE  user_id=? AND folder=? "
            "ORDER  BY uploaded_at DESC",
            user_id,
            folder,
        )

    async def get_file(self, file_id: str):
        return await self.fetchone("SELECT * FROM files WHERE id=?", file_id)

    async def delete_file(self, file_id: str):
        await self.execute("DELETE FROM files WHERE id=?", file_id)

    async def delete_all_files(self, user_id: int):
        rows = await self.fetchall("SELECT path FROM files WHERE user_id=?", user_id)
        for r in rows:
            try:
                Path(r["path"]).unlink(missing_ok=True)
            except Exception:
                pass
        await self.execute("DELETE FROM files WHERE user_id=?", user_id)

    async def update_tags(self, file_id: str, tags: str):
        await self.execute("UPDATE files SET tags=? WHERE id=?", tags, file_id)

    async def update_shared_tags(self, file_id: str, tags: str):
        await self.execute("UPDATE shared_files SET tags=? WHERE id=?", tags, file_id)

    async def search_files(self, user_id: int, term: str, folder: str = ""):
        like = f"%{term}%"
        return await self.fetchall(
            "SELECT * FROM files WHERE user_id=? AND folder=? AND tags LIKE ?",
            user_id,
            folder,
            like,
        )

    async def search_shared_files(self, folder_id: int, term: str):
        like = f"%{term}%"
        return await self.fetchall(
            "SELECT * FROM shared_files WHERE folder_id=? AND tags LIKE ?",
            folder_id,
            like,
        )

    async def delete_all_shared_files(self, folder_id: int):
        rows = await self.fetchall(
            "SELECT path FROM shared_files WHERE folder_id=?",
            folder_id,
        )
        for r in rows:
            try:
                Path(r["path"]).unlink(missing_ok=True)
            except Exception:
                pass
        await self.execute("DELETE FROM shared_files WHERE folder_id=?", folder_id)

    async def get_last_send(
        self, sender: int, target: int, file_id: str
    ) -> Optional[int]:
        row = await self.fetchone(
            "SELECT sent_at FROM send_logs WHERE sender_discord_id=? AND target_discord_id=? AND file_id=?",
            sender,
            target,
            file_id,
        )
        return row["sent_at"] if row else None

    async def update_send_log(self, sender: int, target: int, file_id: str) -> None:
        await self.conn.execute(
            """
            INSERT INTO send_logs(sender_discord_id, target_discord_id, file_id, sent_at)
            VALUES(?,?,?,strftime('%s','now'))
            ON CONFLICT(sender_discord_id, target_discord_id, file_id)
            DO UPDATE SET sent_at=strftime('%s','now')
            """,
            (sender, target, file_id),
        )
        await self.conn.commit()


# ───────────────────────────────────────────
# CLI
# ───────────────────────────────────────────
def _cli():
    import argparse, textwrap, sys

    parser = argparse.ArgumentParser(
        description="DB maintenance helper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """\
            commands:
              init-db                 初期化
              add-user USERNAME [-p PW] [--discord-id ID]
            """
        ),
    )
    parser.add_argument("cmd")
    parser.add_argument("username", nargs="?")
    parser.add_argument("-p", "--password")
    parser.add_argument("--discord-id", type=int)
    args = parser.parse_args()

    async def run():
        if args.cmd == "init-db":
            await init_db()
            print("✔ DB initialized:", DB_PATH)
        elif args.cmd == "add-user":
            pw = args.password or secrets.token_urlsafe(12)
            async with Database() as db:
                await db.add_user(args.discord_id or 0, args.username, pw)
            print("✔ user added:", args.username)
            print("  password:", pw)
        else:
            parser.print_help()
            sys.exit(1)

    asyncio.run(run())


if __name__ == "__main__":
    _cli()
