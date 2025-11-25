# インストールガイド

このガイドでは、ウマ店WordPress自動投稿システムのインストール手順を詳しく説明します。

## 目次

1. [システム要件の確認](#システム要件の確認)
2. [Pythonのインストール](#pythonのインストール)
3. [プロジェクトのセットアップ](#プロジェクトのセットアップ)
4. [WordPressの設定](#wordpressの設定)
5. [Claude APIの設定](#claude-apiの設定)
6. [動作確認](#動作確認)

## システム要件の確認

### Windows

- Windows 11 Home / Pro / Pro for Workstations
- Windows Server 2019 / 2022
- CPU: Intel Core i3以上 または Intel Xeon
- RAM: 4GB以上推奨
- ストレージ: 500MB以上の空き容量

### Python

- Python 3.8以上が必要です

Pythonがインストールされているか確認:

```powershell
python --version
```

## Pythonのインストール

### Windows 11の場合

1. [Python公式サイト](https://www.python.org/downloads/)にアクセス
2. 最新のPython 3.x（3.8以上）をダウンロード
3. インストーラーを実行
4. **重要**: "Add Python to PATH"にチェックを入れる
5. "Install Now"をクリック

### インストール確認

コマンドプロンプトまたはPowerShellで確認:

```powershell
python --version
pip --version
```

## プロジェクトのセットアップ

### 1. リポジトリのクローン

```powershell
# GitHubからクローン
git clone https://github.com/inosuke680-sys/umaten.git
cd umaten
```

Gitがインストールされていない場合は、ZIPファイルをダウンロードして展開してください。

### 2. 仮想環境の作成（推奨）

仮想環境を使用することで、システムのPython環境を汚さずに済みます。

```powershell
# 仮想環境を作成
python -m venv venv

# 仮想環境を有効化
venv\Scripts\activate

# 有効化されると、プロンプトの先頭に (venv) が表示されます
```

### 3. 依存パッケージのインストール

```powershell
# requirements.txtから一括インストール
pip install -r requirements.txt
```

インストールには数分かかる場合があります。

### 4. 設定ファイルの作成

```powershell
# サンプルファイルをコピー
copy config\config.yaml.example config\config.yaml
```

### 5. ディレクトリ構造の確認

以下のディレクトリが存在することを確認してください（自動作成されますが、確認推奨）:

```
umaten/
├── config/
├── logs/
├── output/
│   ├── html/
│   └── metadata/
├── src/
└── templates/
```

## WordPressの設定

### 1. Application Passwordの有効化

WordPress 5.6以降では、Application Passwordsがデフォルトで有効です。

### 2. Application Passwordの作成

1. WordPressダッシュボードにログイン
2. 左メニューから「ユーザー」→「プロフィール」をクリック
3. ページを下にスクロールして「アプリケーションパスワード」セクションを見つける
4. 「新しいアプリケーション名」欄に `Umaten Scraper` と入力
5. 「新しいアプリケーションパスワードを追加」ボタンをクリック
6. 表示されたパスワードをコピー（後で使用）

**注意**: このパスワードは一度しか表示されません。必ずコピーしてください。

### 3. REST APIの確認

ブラウザで以下のURLにアクセスして、REST APIが有効か確認:

```
https://umaten.jp/wp-json/wp/v2
```

JSONデータが表示されればOKです。

### 4. カテゴリの作成

WordPress管理画面で以下のカテゴリを作成してください:

- イタリアン・フレンチ (slug: `italian`)
- うどん・そば (slug: `udon`)
- カフェ・スイーツ (slug: `cafe`)
- しゃぶしゃぶ・すきやき (slug: `sukiyaki`)
- ビュッフェ・食べ放題 (slug: `buffet`)
- ラーメン (slug: `ramen`)
- 中華料理 (slug: `chuka`)
- 寿司・和食 (slug: `washoku`)
- 居酒屋・バー (slug: `izakaya`)
- 洋食・レストラン (slug: `western-food`)
- 焼肉・ステーキ (slug: `yakiniku`)
- 焼鳥・串 (slug: `yakitori`)

## Claude APIの設定

### 1. Anthropicアカウントの作成

1. [Anthropic Console](https://console.anthropic.com/)にアクセス
2. 「Sign Up」をクリックしてアカウントを作成
3. メール認証を完了

### 2. API Keyの取得

1. Consoleにログイン
2. 左メニューから「API Keys」をクリック
3. 「Create Key」ボタンをクリック
4. キーの名前を入力（例: `umaten-scraper`）
5. 生成されたキーをコピー（後で使用）

### 3. 使用量の確認

- 無料枠: 最初のサインアップ時にクレジットが付与される場合があります
- 有料プラン: クレジットカードを登録して利用

## 設定ファイルの編集

`config/config.yaml` をテキストエディタで開き、以下を設定:

```yaml
# WordPress設定
wordpress:
  url: "https://umaten.jp"  # あなたのサイトURL
  username: "your_username"  # WordPressユーザー名
  app_password: "xxxx xxxx xxxx xxxx"  # コピーしたApplication Password

# Claude API設定
claude:
  api_key: "sk-ant-xxxxx"  # コピーしたClaude API Key
  model: "claude-sonnet-4-5-20250929"
  max_tokens: 8000
  temperature: 0.7
```

**重要**: `config.yaml`は `.gitignore` に含まれているため、Gitにコミットされません。

## 動作確認

### 1. WordPress接続テスト

```powershell
python main.py --test-connection
```

成功すると以下のように表示されます:

```
✓ 接続成功!
```

### 2. テスト実行（WordPress投稿なし）

```powershell
python main.py --no-wordpress "https://tabelog.com/hokkaido/A0101/A010103/1067504/"
```

成功すると、`output/html/` にHTMLファイルが生成されます。

### 3. 下書き投稿テスト

```powershell
python main.py "https://tabelog.com/hokkaido/A0101/A010103/1067504/"
```

成功すると、WordPressに下書きとして投稿されます。

### 4. 公開投稿テスト

```powershell
python main.py --publish "https://tabelog.com/hokkaido/A0101/A010103/1067504/"
```

**注意**: いきなり公開する前に、必ず下書きで確認してください。

## トラブルシューティング

### ModuleNotFoundError

依存パッケージが正しくインストールされていません:

```powershell
pip install -r requirements.txt
```

### WordPress接続エラー

1. WordPressサイトのURLが正しいか確認
2. Application Passwordが正しいか確認（スペースは自動で除去されます）
3. ユーザー名が正しいか確認
4. WordPressサイトがhttps（SSL）で接続可能か確認

### Claude APIエラー

1. API Keyが正しいか確認
2. Anthropic Consoleでクレジット残高を確認
3. APIの利用制限（Rate Limit）に達していないか確認

### PermissionError

Windowsでファイルの書き込み権限がない場合:

1. 管理者権限でコマンドプロンプトを実行
2. または、プロジェクトフォルダの場所を変更（例: `C:\Users\YourName\Documents\umaten`）

## 次のステップ

インストールが完了したら、[README.md](README.md)の使用方法セクションを参照してください。

---

問題が解決しない場合は、`logs/umaten_scraper.log` を確認してください。
