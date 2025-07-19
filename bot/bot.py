"""bot/bot.py – Discord Bot + aiohttp Web

・参加者が入室すると DB にユーザ登録し、本人と Bot 製作者にログイン情報を DM
・/resend_login … DM 拒否していた人向けに再送
・/get_login … 製作者(オーナー)が自分用のログイン情報を取得
"""

from __future__ import annotations

# ── stdlib ─────────────────────────────
import logging, os, secrets, hashlib, time
from pathlib import Path
from typing import Optional

# ── third-party ────────────────────────
import discord
from discord import app_commands
from aiohttp import web
import aiohttp
from dotenv import load_dotenv
load_dotenv()
# ── local ──────────────────────────────
from web.app import create_app, _sign_token                  # type: ignore
from bot.db import Database                                  # type: ignore
from bot.commands import setup_commands
import pyotp, qrcode# スラッシュコマンド本体
import base64

import io                # 画像バッファ用
import qrcode            # QR 生成
from .help import setup_help

# ───────────────────────────────────────
# 1. .env
# ───────────────────────────────────────

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
DB_PATH       = Path(os.getenv("DB_PATH", "data/web_discord_server.db"))
PUBLIC_DOMAIN = os.getenv("PUBLIC_DOMAIN", "localhost:9040")
WEB_PORT      = int(os.getenv("PORT", 9040))
OWNER_ID      = int(os.getenv("BOT_OWNER_ID", "0")) or None   # 製作者の ID
DEV_GUILD_ID = int(os.getenv("BOT_GUILD_ID", "0")) or None   # ← ここで定数化
HTTP_TIMEOUT = aiohttp.ClientTimeout(total=60)

# ───────────────────────────────────────
# 2. log
# ───────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger("web_discord")

# ───────────────────────────────────────
# 3. Bot
# ───────────────────────────────────────

def make_otp_link(uri: str) -> str:
    """otpauth://URI → HTTPS 転送リンクに変換"""
    token = base64.urlsafe_b64encode(uri.encode()).decode()
    return f"https://{PUBLIC_DOMAIN}/otp/{token}"

class WebDiscordBot(discord.Client):
    def __init__(self, db_path: Path):
        intents = discord.Intents.default(); intents.members = True
        super().__init__(intents=intents)

        # ① DB 接続まだ。open() は setup_hook で行う
        self.db = Database(db_path)
        self.owner_id = OWNER_ID                         # オーナー ID 定数を保持
        self.web_app: web.Application | None = None
        self.setup_tokens: dict[str, dict] = {}

        # ② Slash 用 CommandTree をここで生成！
        self.tree = app_commands.CommandTree(self)       # ← ★これが無いと AttributeError

        # ③ commands.py の関数をツリーに登録
        setup_commands(self)                             # 必ず tree 生成後に呼ぶ

    async def notify_shared_upload(self, folder_id: int, user: discord.abc.User, file_name: str) -> None:
        """共有フォルダへのアップロードを Webhook 経由で通知"""
        rec = await self.db.get_shared_folder(folder_id)
        url = rec.get("webhook_url") if rec else None
        if not url:
            return
        async with aiohttp.ClientSession(timeout=HTTP_TIMEOUT) as session:
            await session.post(
                url,
                json={"content": f"📥 {user.mention} が `{file_name}` をアップロードしました。"},
            )

    async def on_ready(self):
        await self.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="/help"))
        log.info("Bot ready")

    # --------------- lifecycle ---------------
    async def setup_hook(self):
        # ❶ DB 物理接続
        await self.db.open()

        # ❷ Web サーバー
        self.web_app = create_app(self)
        runner = web.AppRunner(self.web_app)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", WEB_PORT).start()

        # ❸ Slash コマンド同期（1回だけ）
        if DEV_GUILD_ID:
            await self.tree.sync(guild=discord.Object(DEV_GUILD_ID))
        else:
            await self.tree.sync()
        await setup_help(self)


    # --------------- member join -------------
    async def on_member_join(self, member: discord.Member):
        """新規参加者を Web_DB に登録し、ログイン情報 + 2FA QR を DM で送る"""
        # 1) 乱数パスワード生成
        pw = secrets.token_urlsafe(12)

        # 2) TOTP シークレット & QR 作成
        totp   = pyotp.TOTP(pyotp.random_base32())
        secret = totp.secret                          # 32 桁 Base32
        uri    = totp.provisioning_uri(str(member), issuer_name="WDS")
        otp_link = make_otp_link(uri)

        qr_img = qrcode.make(uri)
        buf = io.BytesIO(); qr_img.save(buf, format="PNG"); buf.seek(0)
        setup_token = secrets.token_urlsafe(16)
        if self.web_app:
            self.web_app["setup_tokens"][setup_token] = {
                "username": str(member),
                "password": pw,
                "secret": secret,
                "expires": time.time() + 600,
            }
        setup_link = f"https://{PUBLIC_DOMAIN}/setup/{setup_token}"
        setup_qr = qrcode.make(setup_link)
        setup_buf = io.BytesIO(); setup_qr.save(setup_buf, format="PNG"); setup_buf.seek(0)
        # 3) DB 登録（重複登録を防ぐため 1 回だけ）
        await self.db.add_user(                 # ← 既存シグネチャ通りに
            discord_id = member.id,
            username   = str(member),
            password   = pw
        )

        # 追加フィールドを別 UPDATE で保存
        await self.db.execute(
            "UPDATE users SET totp_secret=?, totp_enabled=1, enc_key=?, totp_verified=0 WHERE discord_id=?",
            secret,
            base64.urlsafe_b64encode(os.urandom(32)).decode(),
            member.id,
        )
        await self.db.commit()

        # 4) DM で送信
        login_url = f"https://{PUBLIC_DOMAIN}/login"
        msg = (
            f"ようこそ **{member.guild.name}**!\n\n"
            "🔑 **Web ログイン情報**\n"
            f"URL: {login_url}\n"
            f"ユーザ名: {member}\n"
            f"パスワード: `{pw}`\n"
            "――――――――――――――――――――\n"
            "🤖 **自動設定 QR**\n"
            "下記リンクか QR を読み取ると自動で設定できます:\n"
            f"{setup_link}\n"
            "――――――――――――――――――――\n"
            "🔐 **二要素認証 (TOTP) を設定してください**\n"
            "QR が読めない場合は下記リンクをタップ:\n"
            f"{otp_link}\n"        # ← HTTPS リンクを送る
            f"`{secret}`           ← 手動入力用シークレット"
        )

        try:
            await member.send(
                msg,
                files=[
                    discord.File(buf, "totp.png"),
                    discord.File(setup_buf, "setup.png"),
                ],
            )
        except discord.Forbidden:
            log.warning("DM blocked for %s", member)

        # 5) 製作者へ通知
        if self.owner_id and (owner := self.get_user(self.owner_id)):
            try:
                await owner.send(f"👤 **新規登録**: {member}\n{msg}")
            except discord.Forbidden:
                log.warning("Owner DM blocked")

    async def on_message(self, message: discord.Message):
        # ボット自身や添付なしのメッセージは無視
        if message.author.bot or not message.attachments:
            return

        folder_row = await self.db.fetchone(
            "SELECT id FROM shared_folders WHERE channel_id = ?", message.channel.id
        )
        if not folder_row:
            return  # 共有フォルダ外のチャンネルの場合無視

        folder_id = folder_row["id"]

        for attachment in message.attachments:
            file_data = await attachment.read()
            fid = str(uuid.uuid4())
            file_path = DATA_DIR / fid
            file_path.write_bytes(file_data)

            await self.db.execute(
                "INSERT INTO shared_files (id, folder_id, file_name, path) VALUES (?, ?, ?, ?)",
                fid, folder_id, attachment.filename, str(file_path)
            )
            await self.notify_shared_upload(folder_id, message.author, attachment.filename)

        await self.db.commit()

    # --------------- /resend_login ----------
    @app_commands.command(name="resend_login", description="DM でログイン情報を再送します。")
    async def resend_login(self, inter: discord.Interaction):
        await inter.response.defer(ephemeral=True)
        if not await self.db.user_exists(inter.user.id):
            await inter.followup.send("ユーザ登録が見つかりません。", ephemeral=True); return

        new_pw = secrets.token_urlsafe(12)
        await self.add_user(inter.user.id, str(inter.user), new_pw)

        login_url = f"https://{PUBLIC_DOMAIN}/login"
        dm_text = (
            f"🔑 **再発行されたログイン情報**\nURL: {login_url}\n"
            f"ユーザ名: {inter.user}\nパスワード: `{new_pw}`"
        )
        try:
            await inter.user.send(dm_text)
            await inter.followup.send("DM を送信しました！", ephemeral=True)
            # 製作者へ通知
            if self.owner_id:
                owner = self.get_user(self.owner_id)
                if owner:
                    await owner.send(f"🔄 **再発行**: {inter.user}\n{dm_text}")
        except discord.Forbidden:
            await inter.followup.send("❌ DM が拒否されています。", ephemeral=True)

# ───────────────────────────────────────
# 4. main
# ───────────────────────────────────────
def main():
    log.info("logging in using static token")
    WebDiscordBot(DB_PATH).run(DISCORD_TOKEN)

if __name__ == "__main__":
    main()
