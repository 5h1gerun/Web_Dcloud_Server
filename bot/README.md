# Discord Bot

このディレクトリには Web Dcloud Server のボット側コードが含まれています。
ボットはファイル共有用 Web サーバーを同時に起動し、Discord 上の操作だけで
アップロード・共有・ダウンロードを行えるように設計されています。

## 主な機能
- サーバー参加時に自動登録し、ログイン情報と二要素認証(QRコード)をDMで送信
- `/upload` コマンドによるファイルアップロードと `/myfiles` での一覧表示
- 共有フォルダを作成しメンバーを招待する `/create_shared_folder`
- 各種ファイル操作(削除・タグ付け・共有状態切替・リンク取得)
- ダウンロードリンクに `?preview=1` を付けることでブラウザ上でのプレビューを提供
- 管理者向けコマンド `/sync` `/admin_reset_totp` など
- `help` コマンドで全コマンドの詳細を確認可能

## コマンド一覧
`help` コマンドでは以下のコマンドを選択して詳細説明が表示されます。
- `ping` – レイテンシ確認
- `myfiles` – 自分のファイル一覧をページ表示
- `upload` – ファイルをアップロード
- `delete` / `delete_all` – 指定ファイルまたは全ファイル削除
- `set_tags` – ファイルにタグを設定
- `getfile` – 保存済みファイルを再送信
- `sendfile` – 指定ユーザーへファイルをDM送信
  (同一ファイルの連続送信は `SEND_INTERVAL_SEC` 秒の間隔が必要)
- `share` / `getlink` – 共有状態切替とダウンロードリンク取得
- `create_shared_folder` – 共有フォルダ作成
- `search_files` – タグで自分のファイルを検索
- `manage_shared_folder` – 共有フォルダのメンバー管理
- `shared_files` – 参加中フォルダ内のファイル一覧
- `delete_shared_folder` / `remove_shared_folder` – フォルダ削除・退出
- `upload_shared` – 共有フォルダへファイルアップロード
- `shared_delete_all` – 共有フォルダ内の全ファイル削除
- `set_shared_tags` – 共有フォルダ内ファイルのタグ設定
- `add_shared_webhook` – 既存共有フォルダへWebhookを自動設定
- `cleanup_shared` – 空の共有フォルダを一括削除
- `enable_totp` – 二要素認証を有効化
- `admin_reset_totp` – 管理者によるTOTPリセット

詳細な動作や必要な環境変数については上位ディレクトリの `README.md` を参照してください。

## Webhook 通知
共有フォルダのチャンネルに Webhook を登録すると、アップロードを自動的に通知できます。
`/add_shared_webhook` コマンドを実行すると、そのチャンネルに `WDS Notify` という
Webhook を作成（既に存在する場合は再利用）し、データベースへ URL を登録します。
以降そのフォルダへファイルがアップロードされるたびに、Webhook 経由で
「ユーザー名 が `<ファイル名>` をアップロードしました」というメッセージが投稿されます。
