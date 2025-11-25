# ウマ店 WordPress自動投稿システム

食べログなどのグルメサイトから店舗情報を自動スクレイピングし、Claude AIで高品質な記事を生成してWordPressに自動投稿するシステムです。

## 主な機能

- 🕷️ **Webスクレイピング**: 食べログから店舗情報・写真・レビューを自動取得
- 🤖 **AI記事生成**: Claude Sonnet 4.5で高品質な記事を自動生成
- 📝 **WordPress自動投稿**: REST APIを使用して自動投稿
- 🎨 **HTMLテンプレート対応**: カスタムHTMLテンプレートに対応
- 🔒 **アクセス制限対策**: User-Agent切り替え、遅延処理、リトライ機能
- 💻 **クロスプラットフォーム**: Windows 11 / Server対応

## システム要件

### 対応OS
- Windows 11 Home
- Windows 11 Pro
- Windows 11 Pro for Workstations
- Windows Server 2019/2022

### 対応CPU
- Intel Core iシリーズ (i3/i5/i7/i9)
- Intel Xeon プロセッサー

### ソフトウェア要件
- Python 3.8以上
- インターネット接続

## インストール

### 1. リポジトリをクローン

```bash
git clone https://github.com/inosuke680-sys/umaten.git
cd umaten
```

### 2. 仮想環境を作成（推奨）

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. 依存パッケージをインストール

```bash
pip install -r requirements.txt
```

### 4. 設定ファイルを作成

```bash
# Windowsの場合
copy config\config.yaml.example config\config.yaml

# Linux/Macの場合
cp config/config.yaml.example config/config.yaml
```

### 5. 設定ファイルを編集

`config/config.yaml` を開いて、以下の情報を設定してください：

```yaml
# WordPress設定
wordpress:
  url: "https://umaten.jp"  # あなたのWordPressサイトURL
  username: "your_username"
  app_password: "xxxx xxxx xxxx xxxx"  # Application Password

# Claude API設定
claude:
  api_key: "sk-ant-xxxxx"  # Anthropic API Key
```

## WordPress Application Passwordの取得方法

1. WordPressダッシュボードにログイン
2. 「ユーザー」→「プロフィール」を開く
3. 下にスクロールして「Application Passwords」セクションを見つける
4. 新しいアプリケーション名を入力（例: "Umaten Scraper"）
5. 「新しいアプリケーションパスワードを追加」をクリック
6. 表示されたパスワードをコピーして `config.yaml` に設定

## Claude API Keyの取得方法

1. [Anthropic Console](https://console.anthropic.com/)にアクセス
2. アカウントを作成またはログイン
3. 「API Keys」セクションで新しいキーを作成
4. キーをコピーして `config.yaml` に設定

## 使用方法

### 基本的な使い方

```bash
# 食べログのURLを指定して実行（下書きとして保存）
python main.py "https://tabelog.com/hokkaido/A0101/A010103/1067504/"

# 公開状態で投稿
python main.py --publish "https://tabelog.com/hokkaido/A0101/A010103/1067504/"

# WordPress投稿なし（HTMLファイルのみ生成）
python main.py --no-wordpress "https://tabelog.com/hokkaido/A0101/A010103/1067504/"
```

### WordPress接続テスト

```bash
python main.py --test-connection
```

### カスタム設定ファイルを使用

```bash
python main.py --config config/my_config.yaml "https://tabelog.com/..."
```

## プロジェクト構造

```
umaten/
├── main.py                    # メインスクリプト
├── requirements.txt           # 依存パッケージ
├── README.md                  # このファイル
├── config/
│   ├── config.yaml.example    # 設定ファイルサンプル
│   ├── config.yaml            # 実際の設定ファイル（要作成）
│   └── prompt_template.txt    # Claude用プロンプトテンプレート
├── src/
│   ├── __init__.py
│   ├── scraper.py             # スクレイピングモジュール
│   ├── article_generator.py   # 記事生成モジュール
│   └── wordpress_publisher.py # WordPress投稿モジュール
├── templates/
│   └── restaurant_template.html  # HTMLテンプレート（オプション）
├── logs/                      # ログファイル
└── output/                    # 生成されたファイル
    ├── html/                  # HTMLファイル
    └── metadata/              # メタデータJSON
```

## 設定項目詳細

### スクレイピング設定

```yaml
scraping:
  min_delay: 2          # リクエスト間の最小遅延（秒）
  max_delay: 5          # リクエスト間の最大遅延（秒）
  max_retries: 3        # 最大リトライ回数
  timeout: 30           # タイムアウト（秒）
```

### カテゴリマッピング

食べログのカテゴリをWordPressのカテゴリスラッグにマッピングします：

```yaml
category_mapping:
  "イタリアン": "italian"
  "ラーメン": "ramen"
  "寿司": "washoku"
  # ...
```

## トラブルシューティング

### WordPress投稿が失敗する

1. Application Passwordが正しく設定されているか確認
2. WordPressサイトがREST APIを有効にしているか確認
3. 接続テストを実行: `python main.py --test-connection`

### スクレイピングが失敗する

1. URLが正しいか確認
2. インターネット接続を確認
3. 遅延設定を増やす（`config.yaml`の`min_delay`/`max_delay`）

### Claude API エラー

1. API Keyが正しく設定されているか確認
2. APIの利用制限を確認
3. クレジットが十分にあるか確認

## アクセス制限対策

本システムは以下の対策を実装しています：

- **User-Agent切り替え**: 複数のUser-Agentからランダムに選択
- **遅延処理**: リクエスト間にランダムな遅延を挿入
- **リトライ機能**: 失敗時に自動でリトライ
- **タイムアウト設定**: 長時間のリクエストを防止

## ライセンス

MIT License

## 注意事項

- **利用規約遵守**: スクレイピング対象サイトの利用規約を必ず確認してください
- **著作権**: 取得した情報の著作権に注意してください
- **節度ある利用**: サーバーに負荷をかけないよう、適切な遅延を設定してください
- **商用利用**: 商用利用する場合は、対象サイトの利用規約を確認してください

## サポート

問題が発生した場合は、以下をご確認ください：

1. ログファイル: `logs/umaten_scraper.log`
2. 設定ファイル: `config/config.yaml`
3. エラーメッセージ

## 開発者情報

- プロジェクト: ウマ店 (umaten.jp)
- バージョン: 1.0.0
- 最終更新: 2025年1月

## 今後の改善予定

- [ ] 他のグルメサイト対応（ぐるなび、Retty等）
- [ ] バッチ処理機能（複数URL一括処理）
- [ ] Selenium対応（動的コンテンツ）
- [ ] プロキシ対応
- [ ] GUI版の開発
- [ ] スケジュール実行機能
- [ ] エラー通知機能（メール・Slack）

## 貢献

プルリクエストを歓迎します！大きな変更の場合は、まずIssueを開いて変更内容を議論してください。

---

**Happy Scraping! 🍜🍣🍕**
