以下はこのリポジトリ用の nginx 逆プロキシ設定サンプルです。アプリは標準で 127.0.0.1:9040（WebSocket 対応／大容量アップロード）で待ち受けます。必要に応じて server_name、証明書パス、エイリアス先の実ディレクトリを置き換えてください。

既存の参考例
-既に実例があります: nginx/sites-enabled/web_discord_server.conf:1（DuckDNS 向け・非標準ポート利用）。下の汎用版は標準の 80/443 前提です。

# 標準構成（80/443・HTTP→HTTPS・静的配信最適化）

```bash
# /etc/nginx/sites-available/web_discord_server.conf (sample)
# Reverse proxy for Web_Discord_Server (aiohttp on 127.0.0.1:9040)

# 1) HTTP: redirect + ACME
server {
    listen 80;
    listen [::]:80;
    server_name YOUR_PUBLIC_DOMAIN;  # 例: files.example.com

    client_max_body_size 50G;

    # certbot 用 ACME challenge
    location ^~ /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    # 上記以外は HTTPS へ
    location / { return 301 https://$host$request_uri; }
}

# 2) HTTPS vhost (HTTP/2)
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name YOUR_PUBLIC_DOMAIN;  # 例: files.example.com

    client_max_body_size 50G;

    # TLS（certbot 管理を想定）
    ssl_certificate     /etc/letsencrypt/live/YOUR_PUBLIC_DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/YOUR_PUBLIC_DOMAIN/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;

    # 静的ファイルを nginx で直配信（パスは環境に合わせて変更）
    location /static/ {
        alias /path/to/Web_Discord_Server/web/static/;
        try_files $uri $uri/ =404;
        access_log off;
        expires 7d;
    }

    # プレビュー画像（アプリ生成）
    location /previews/ {
        alias /path/to/Web_Discord_Server/data/previews/;
        try_files $uri =404;
        access_log off;
        expires 1h;
    }

    # HLS 出力（m3u8/ts の MIME 設定）
    location /hls/ {
        alias /path/to/Web_Discord_Server/data/hls/;
        types { application/vnd.apple.mpegurl m3u8; video/mp2t ts; }
        add_header Cache-Control no-cache;
        try_files $uri =404;
        access_log off;
    }

    # それ以外は aiohttp へプロキシ
    location / {
        # 大容量アップロードをバッファせずストリーム転送
        proxy_request_buffering off;
        proxy_buffering off;

        proxy_pass         http://127.0.0.1:9040;  # PORT を変更した場合は調整
        proxy_http_version 1.1;

        # WebSocket
        proxy_set_header   Upgrade $http_upgrade;
        proxy_set_header   Connection "upgrade";

        # Forwarded ヘッダ
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;

        # タイムアウト（必要に応じて調整）
        proxy_connect_timeout 60s;
        proxy_send_timeout    300s;
        proxy_read_timeout    300s;
    }
}
```

# ダウンロード専用ドメイン（任意・DOWNLOAD_DOMAIN 用）

```bash
# /etc/nginx/sites-available/web_discord_server_download_only.conf (sample)
# Only proxies download-related endpoints to the same aiohttp backend

# 1) HTTP: redirect + ACME
server {
    listen 80;
    listen [::]:80;
    server_name YOUR_DOWNLOAD_DOMAIN;  # 例: downloads.example.com

    client_max_body_size 50G;

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / { return 301 https://$host$request_uri; }
}

# 2) HTTPS vhost
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name YOUR_DOWNLOAD_DOMAIN;

    client_max_body_size 50G;

    ssl_certificate     /etc/letsencrypt/live/YOUR_DOWNLOAD_DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/YOUR_DOWNLOAD_DOMAIN/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    # ダウンロード関連だけをアプリに転送
    location ^~ /download/ {
        proxy_request_buffering off;
        proxy_buffering off;
        proxy_pass         http://127.0.0.1:9040;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout    300s;
        proxy_read_timeout    300s;
    }

    location ^~ /shared/download/ {
        proxy_request_buffering off;
        proxy_buffering off;
        proxy_pass         http://127.0.0.1:9040;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }

    location ^~ /f/ {
        proxy_request_buffering off;
        proxy_buffering off;
        proxy_pass         http://127.0.0.1:9040;
        proxy_http_version 1.1;
        proxy_set_header   Host $host;
        proxy_set_header   X-Real-IP $remote_addr;
        proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }

    # プレビュー/HLS を直接配信したい場合（任意）
    location /previews/ {
        alias /path/to/Web_Discord_Server/data/previews/;
        try_files $uri =404;
        access_log off;
        expires 1h;
    }
    location /hls/ {
        alias /path/to/Web_Discord_Server/data/hls/;
        types { application/vnd.apple.mpegurl m3u8; video/mp2t ts; }
        add_header Cache-Control no-cache;
        try_files $uri =404;
        access_log off;
    }

    # 上記以外は 404（ダウンロード専用ドメインとして運用する場合）
    location / { return 404; }
}
```
# 反映手順（例・Ubuntu/Debian）
- 証明書用 ACME ルート作成: sudo mkdir -p /var/www/certbot && sudo chown www-data:www-data /var/www/certbot
- サンプルを配置・編集: /etc/nginx/sites-available/ に保存し server_name とパスを調整
- 既存の実例は nginx/sites-enabled/web_discord_server.conf:1 にあります（DuckDNS/非標準ポート運用の参考）。