import os
import io
import json
from pathlib import Path
from typing import List, Tuple, Dict, Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.auth.transport.requests import Request

# これまでは drive.file スコープのみを利用していたが、
# それではアプリが作成したファイルしか取得できないため
# 他のファイルが一覧に表示されない。
# Drive 上の全てのファイルを読み取れるよう drive.readonly を追加する。
_SCOPES = [
    # 既存の drive.file に加え、全てのファイルを参照できるよう
    # drive.readonly も要求する
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.readonly",
]
_CRED_PATH = os.getenv("GDRIVE_CREDENTIALS")


def build_flow(redirect_uri: str, *, state: Optional[str] = None) -> Flow:
    if not _CRED_PATH:
        raise RuntimeError("GDRIVE_CREDENTIALS is not set")
    return Flow.from_client_secrets_file(
        _CRED_PATH,
        scopes=_SCOPES,
        redirect_uri=redirect_uri,
        state=state,
    )


def _service_from_token(token_json: str):
    info = json.loads(token_json)
    if "refresh_token" not in info:
        raise ValueError("リフレッシュトークンがありません。/gdrive_auth で再認証してください")
    creds = Credentials.from_authorized_user_info(info, _SCOPES)
    if not creds.valid:
        creds.refresh(Request())
    service = build("drive", "v3", credentials=creds)
    return service, creds.to_json()


def upload_file(local_path: Path, filename: str, token_json: str) -> Tuple[str, str]:
    service, token_json = _service_from_token(token_json)
    file_metadata = {"name": filename}
    media = MediaFileUpload(local_path)
    file = (
        service.files()
        .create(body=file_metadata, media_body=media, fields="id")
        .execute()
    )
    return file.get("id"), token_json


def download_file(
    file_id: str,
    token_json: str,
    acknowledge_abuse: bool = False,
) -> Tuple[bytes, str]:
    """Download file bytes.

    acknowledge_abuse=True を指定すると、Google により危険と判定された
    ファイルでもダウンロードを試みます。
    """
    service, token_json = _service_from_token(token_json)
    request = service.files().get_media(
        fileId=file_id, acknowledgeAbuse=acknowledge_abuse
    )
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return fh.getvalue(), token_json


def get_file_name(file_id: str, token_json: str) -> Tuple[str, str]:
    service, token_json = _service_from_token(token_json)
    meta = service.files().get(fileId=file_id, fields="name").execute()
    return meta.get("name", file_id), token_json


def list_files(
    token_json: str, page_size: int = 20
) -> Tuple[List[Dict[str, str]], str]:
    """Return a list of recent files on Drive."""
    service, token_json = _service_from_token(token_json)
    res = (
        service.files()
        .list(pageSize=page_size, fields="files(id,name,mimeType)")
        .execute()
    )
    return res.get("files", []), token_json


def search_files(
    token_json: str, query: str, page_size: int = 20
) -> Tuple[List[Dict[str, str]], str]:
    """Search Drive files by name."""
    service, token_json = _service_from_token(token_json)
    safe_q = query.replace("'", "\\'")
    res = (
        service.files()
        .list(
            pageSize=page_size,
            q=f"name contains '{safe_q}'",
            fields="files(id,name,mimeType)"
        )
        .execute()
    )
    return res.get("files", []), token_json
