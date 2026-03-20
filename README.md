# TVRecTopic

録画番組の管理と、Gemini を活用したトピック（チャプター）自動抽出機能を備えた Web ベースの録画ビューワーです。

## 主な機能
- **録画機能**: 地上波・BS・CS の予約録画および手動録画。
- **録画番組の管理・視聴**: ブラウザから録画済み番組を一覧・再生できます。
- **AI トピック抽出**: Google Gemini API を使用して、番組内容からトピックを自動生成し、プレイリストに表示します。
- **CS/BS/GR 対応**: 各種放送波の録画・視聴に対応。

## 動作環境
- **OS**: Ubuntu 22.04 で動作確認済み
- **ハードウェアエンコード推奨**: Intel CPU (QSV) 、 NVIDIA GPU (NVENC) は FFmpeg オプション設定あり

## Linux インストール手順

### 1. リポジトリのクローン
```bash
git clone https://github.com/yasuyuki-bot/tvrectopic.git
cd tvrectopic
```

### 2. インストールスクリプトの実行
```bash
chmod +x install_ubuntu.sh
./install_ubuntu.sh
```
※ スクリプトは Node.js、Python venv、依存ライブラリのインストール、フロントエンドのビルド、systemd サービスの設定（`tvrectopic.service`）を自動で行います。

### 3. チューナー・外部ツールの設定
録画、視聴および番組情報の取得には、以下の外部ツールが必要です。事前にインストールし、パスを通しておいてください。
`recdvb` または `recpt1` のいずれかを環境に合わせてインストールしてください。
以下のツールで動作確認を行っています：
- **FFmpeg**: リアルタイム視聴・変換に必須
- **recdvb**: [https://github.com/kaikoma-soft/recdvb](https://github.com/kaikoma-soft/recdvb)
- **recpt1**: [https://github.com/stz2012/recpt1](https://github.com/stz2012/recpt1)
- **epgdump**: [https://github.com/Piro77/epgdump](https://github.com/Piro77/epgdump)
- **Caption2Ass**: 字幕抽出に使用（[https://github.com/iGlitch/Caption2Ass](https://github.com/iGlitch/Caption2Ass) を Linux 用に改変して同梱）

### 4. サービスの管理
以下のコマンドで、OS 起動時に自動でサービスが開始されるように登録し、起動します：
```bash
sudo systemctl enable --now tvrectopic
```
※ `tvrectopic` と `tvrectopic.service` はどちらを指定しても動作は同じです。

**その他のサービス操作コマンド:**
- **起動**: `sudo systemctl start tvrectopic`
- **停止**: `sudo systemctl stop tvrectopic`
- **再起動**: `sudo systemctl restart tvrectopic`
- **ログの確認**: `sudo journalctl -u tvrectopic -f`

## ブラウザからの接続
インストール完了後、以下の URL から管理画面にアクセスできます：
`http://<サーバーのIPアドレス>:8000`
（ローカル環境の場合は `http://localhost:8000`）

## 初期設定項目
ブラウザで管理画面を開き、設定アイコン（歯車）から以下の項目をまず設定してください。

### 1. 録画設定タブ
- **6. 録画システム・実行ファイルパス**: 使用する録画コマンド（recdvb または recpt1）を選択してください。
- **1. 保存先フォルダ**: 録画ファイルを保存するディレクトリの絶対パスを入力してください。

### 2. EPGタブ
- **2. チューナー数設定**: 接続されている物理チューナーの数を設定してください。
- **3. 地上波チャンネルスキャン**: チャンネルスキャンを実行してチャンネルリストを生成してください。
- **1. EPG手動更新**: 番組情報を取得するために実行してください。

### 3. 再生タブ
- **3. FFmpegコマンドオプション**: **重要：TSファイルの直接再生はできません。** H.264 へのリアルタイム変換が必要です。ご使用のハードウェア（QSV/NVENC等）に合わせて最適なオプションを選択してください。

### 4. トピックタブ
- **2. Gemini API キー**: トピック自動抽出を利用するには、Google AI Studio で取得した API キーを「トピック」タブ内の「2. Gemini API キー」に入力して保存してください。

## ライセンス
本プロジェクトは **GNU General Public License v3.0 (GPLv3)** の下で公開されています。
詳細は [LICENSE](file:///c:/Users/rujas/Documents/GitHub/tvrectopic/LICENSE) ファイルを参照してください。

GPLv3 を適用しているため、本コードを改変して配布・公開する場合は、同じ GPLv3 ライセンスの下でソースコードを公開する必要があります。
