import discord
from discord import app_commands
from typing import Dict, Any

# —————————————————————————————————————
# 詳細なコマンド仕様を一から定義（全コマンド含む）
# —————————————————————————————————————
COMMAND_SPECS: Dict[str, Dict[str, Any]] = {
    "ping": {
        "description": (
            "⚡️ **ping** コマンドは、ボットとDiscordサーバー間の通信遅延を測定し、ユーザーにミリ秒単位で表示します。"
            " ゲーム中や高頻度な操作を行う際に、ボットの応答性を確認するのに最適です。"
        ),
        "options": []
    },
    "myfiles": {
        "description": (
            "📂 **myfiles** コマンドは、ユーザーが過去にアップロードしたファイルを最大10件ずつのページ形式で一覧表示します。"
            " ファイル名、アップロード日時、サイズなどの詳細情報を含み、リアクションでページ移動が可能です。"
        ),
        "options": []
    },
    "upload": {
        "description": (
            "⬆️ **upload** コマンドは、指定したファイルをDiscordにアップロードし、自動でサーバー内ストレージに保存します。"
            " 画像(png/jpeg)、動画(mp4/WEBM)など多くのフォーマットに対応し、Nitroプランによるサイズ上限も自動判定されます。"
        ),
        "options": [
            {
                "name": "file",
                "type": "Attachment",
                "required": True,
                "description": "アップロードしたいファイルを添付してください。最大サイズは利用プランによって異なります。"
            }
        ]
    },
    "delete": {
        "description": (
            "🗑️ **delete** コマンドは、指定したファイルIDのファイルを永久に削除します。"
            " 操作後の復元はできないため、IDの指定ミスに注意してください。"
        ),
        "options": [
            {
                "name": "file_id",
                "type": "String",
                "required": True,
                "description": "削除対象のファイルID。`myfiles`コマンドで確認したIDを指定します。"
            }
        ]
    },
    "delete_all": {
        "description": (
            "🗑️ **delete_all** コマンドは、自分がアップロードしたすべてのファイルを一括削除します。",
            " 容量整理や退会時に便利ですが、削除後は復元できません。"
        ),
        "options": []
    },
    "set_tags": {
        "description": (
            "🏷️ **set_tags** コマンドは、指定したファイルに任意のタグ文字列を設定します。",
            " 検索や整理のために複数タグをカンマ区切りで付与できます。"
        ),
        "options": [
            {"name": "file_id", "type": "String", "required": True, "description": "タグを付与するファイルID"},
            {"name": "tags",    "type": "String", "required": True, "description": "設定するタグ（カンマ区切り）"}
        ]
    },
    "getfile": {
        "description": (
            "📤 **getfile** コマンドは、保存済みのファイルを再度Discordに送信します。"
            " サイズ制限を超える場合は、安全なダウンロードリンクを発行し、DMで送信します。"
        ),
        "options": [
            {
                "name": "file_id",
                "type": "String",
                "required": True,
                "description": "再送信したいファイルのIDを指定してください。"
            }
        ]
    },
    "shared_delete_all": {
        "description": (
            "🧺 **shared_delete_all** コマンドは、指定した共有フォルダ内のファイルをすべて削除します。",
            " フォルダ管理者やメンバーが整理したい際に利用します。"
        ),
        "options": [
            {"name": "channel", "type": "TextChannel", "required": True, "description": "対象となる共有フォルダチャンネル"}
        ]
    },
    "set_shared_tags": {
        "description": (
            "🏷️ **set_shared_tags** コマンドは、共有フォルダ内のファイルにタグを設定します。",
            " 権限を持つメンバーが整理しやすいようにタグ付けを行います。"
        ),
        "options": [
            {"name": "file_id", "type": "String", "required": True, "description": "タグを変更するファイルID"},
            {"name": "tags",    "type": "String", "required": True, "description": "設定するタグ（カンマ区切り）"}
        ]
    },
    "share": {
        "description": (
            "🔗 **share** コマンドは、指定したファイルの共有状態をオン/オフで切り替えます。"
            " 共有有効化すると、他ユーザーが`getlink`でダウンロードリンクを取得できるようになります。"
        ),
        "options": [
            {
                "name": "file_id",
                "type": "String",
                "required": True,
                "description": "共有設定を変更したいファイルIDを指定します。"
            }
        ]
    },
    "getlink": {
        "description": (
            "🌐 **getlink** コマンドは、共有中または所有するファイルの安全なダウンロードリンクを生成します。"
            " リンクには有効期限が設定され、一定時間後に無効化されます。"
        ),
        "options": [
            {
                "name": "file_id",
                "type": "String",
                "required": True,
                "description": "リンクを生成したいファイルIDを指定してください。"
            }
        ]
    },
    "get_login": {
        "description": (
            "🔒 **get_login** コマンドは、Botオーナー専用のコマンドです。"
            " ボットの内部設定や管理用ログイン情報をDMで取得できます。"
        ),
        "options": []
    },
    "sync": {
        "description": (
            "🔄 **sync** コマンドは、スラッシュコマンド定義をDiscordサーバーに同期します。"
            " 新規追加や変更を即時反映させたい場合に使用してください（オーナー専用）。"
        ),
        "options": []
    },
    "create_shared_folder": {
        "description": (
            "📁 **create_shared_folder** コマンドは、新しい共有フォルダを作成し、指定したメンバーと権限を共有します。"
            " フォルダ名と招待メンバーを指定することで、共同編集が可能になります。"
        ),
        "options": [
            {"name": "folder_name", "type": "String", "required": True, "description": "作成する共有フォルダの名称。"},
            {"name": "members", "type": "String", "required": True, "description": "共有するユーザーをメンション形式で指定（例: @User1 @User2）。"}
        ]
    },
    "manage_shared_folder": {
        "description": (
            "🛠️ **manage_shared_folder** コマンドは、既存の共有フォルダのメンバー権限を変更できます。"
            " メンバー追加や削除、閲覧/編集権限の設定を行います。"
        ),
        "options": [
            {"name": "channel", "type": "TextChannel", "required": True, "description": "管理対象の共有フォルダチャンネルを指定。"}
        ]
    },
    "shared_files": {
        "description": (
            "👥 **shared_files** コマンドは、参加中のすべての共有フォルダ内のファイル一覧を表示します。"
            " 各フォルダごとにファイル数や最新更新日時も確認可能です。"
        ),
        "options": []
    },
    "delete_shared_folder": {
        "description": (
            "❌ **delete_shared_folder** コマンドは、共有フォルダ用のチャンネルとデータベース記録を一括削除します。"
            " 削除後は復旧できないため、注意して実行してください。"
        ),
        "options": [
            {"name": "channel", "type": "TextChannel", "required": True, "description": "削除する共有フォルダチャンネルを指定。"}
        ]
    },
    "remove_shared_folder": {
        "description": (
            "🚫 **remove_shared_folder** コマンドは、指定した共有フォルダから退出またはフォルダ自体を削除します。"
            " 退出のみの場合、他のメンバーは影響を受けません。"
        ),
        "options": []
    },
    "upload_shared": {
        "description": (
            "📨 **upload_shared** コマンドは、特定の共有フォルダチャンネルにファイルをアップロードし、"
            " メンバーと即時共有します。ファイルタイプやサイズは通常の`upload`と同様です。"
        ),
        "options": [
            {"name": "channel", "type": "TextChannel", "required": True, "description": "アップロード先の共有フォルダチャンネル。"},
            {"name": "file",    "type": "Attachment",  "required": True, "description": "共有フォルダにアップロードするファイル。"}
        ]
    },
    "add_shared_webhook": {
        "description": (
            "🔔 **add_shared_webhook** コマンドは、既存の共有フォルダ用チャンネルに",
            " `WDS Notify` Webhook を作成(または再利用)し、URL を自動登録します。"
        ),
        "options": [
            {"name": "channel", "type": "TextChannel", "required": True, "description": "Webhook を設定する共有フォルダチャンネル。"}
        ]
    },
    "cleanup_shared": {
        "description": (
            "🧹 **cleanup_shared** コマンドは、空の共有フォルダを一括削除し、不要なチャンネルを整理します。"
            " 定期的なメンテナンス時に有用です。"
        ),
        "options": []
    },
    "enable_totp": {
        "description": (
            "🔐 **enable_totp** コマンドは、二要素認証を有効化し、QRコードをDMで送信します。"
            " アプリでQRを読み込むことで、TOTPコード生成が可能になります。"
        ),
        "options": []
    },
    "admin_reset_totp": {
        "description": (
            "🛡️ **admin_reset_totp** コマンドは、管理者専用で指定ユーザーのTOTP認証をリセットします。"
            " リセット後、ユーザーは再度TOTP設定を行う必要があります。"
        ),
        "options": [
            {"name": "user", "type": "User", "required": True, "description": "TOTPをリセットしたいユーザーをメンションで指定。"}
        ]
    }
}

class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        options = [
            discord.SelectOption(
                label=f"/{name}",
                value=name,
                description=(spec["description"].replace("**", "")[:80] + "…" if len(spec["description"]) > 80 else spec["description"])  
            )
            for name, spec in COMMAND_SPECS.items()
        ]
        select = discord.ui.Select(
            placeholder="🔍 コマンドを選択してください",
            options=options,
            min_values=1,
            max_values=1
        )
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        name = interaction.data["values"][0]
        spec = COMMAND_SPECS[name]
        embed = discord.Embed(
            title=f"/{name}",
            description=spec["description"],
            color=discord.Color.blue()
        )
        if spec["options"]:
            for opt in spec["options"]:
                field_name = f"{opt['name']} ({opt['type']}){' *' if opt['required'] else ''}"
                embed.add_field(name=field_name, value=opt['description'], inline=False)
        else:
            embed.add_field(name="オプション", value="なし", inline=False)
        await interaction.response.edit_message(embed=embed, view=self)

async def setup_help(bot: discord.Client):
    @bot.tree.command(
        name="help",
        description="📖 利用可能なコマンド一覧を表示し、詳細ガイドを確認します。"
    )
    async def _help(inter: discord.Interaction):
        await inter.response.defer(ephemeral=True)
        view = HelpView()
        await inter.followup.send(
            content="❓ 下のプルダウンからコマンドを選択し、詳細を確認してください。",
            view=view,
            ephemeral=True
        )
