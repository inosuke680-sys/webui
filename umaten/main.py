#!/usr/bin/env python3
"""
ウマ店 WordPress自動投稿システム - メインスクリプト

使用方法:
    python main.py <食べログURL>
    python main.py --config config/config.yaml <食べログURL>
    python main.py --publish <食べログURL>  # 下書きではなく公開
"""

import sys
import argparse
import yaml
import json
import logging
from pathlib import Path
from datetime import datetime
from colorama import init, Fore, Style

# プロジェクトのsrcディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from scraper import RestaurantScraper
from article_generator import ArticleGenerator
from wordpress_publisher import WordPressPublisher

# Coloramaを初期化
init(autoreset=True)


def setup_logging(config: dict):
    """ロギングを設定"""
    log_config = config.get('logging', {})
    log_level = log_config.get('level', 'INFO')
    log_file = log_config.get('file', 'logs/umaten_scraper.log')

    # ログディレクトリを作成
    log_dir = Path(log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    # ロギング設定
    logging.basicConfig(
        level=getattr(logging, log_level),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )


def load_config(config_path: str) -> dict:
    """設定ファイルを読み込む"""
    config_file = Path(config_path)

    if not config_file.exists():
        print(f"{Fore.RED}✗ 設定ファイルが見つかりません: {config_path}")
        print(f"{Fore.YELLOW}? config/config.yaml.example をコピーして config/config.yaml を作成してください")
        sys.exit(1)

    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    return config


def save_output(data: dict, output_type: str, config: dict):
    """出力データを保存"""
    output_config = config.get('output', {})

    if output_type == 'html' and output_config.get('save_html', True):
        output_dir = Path(output_config.get('html_dir', 'output/html'))
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{data.get('slug', 'article')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        filepath = output_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(data.get('html_content', ''))

        logging.info(f"HTML saved to: {filepath}")
        print(f"{Fore.GREEN}✓ HTMLを保存しました: {filepath}")

    elif output_type == 'metadata' and output_config.get('save_metadata', True):
        output_dir = Path(output_config.get('metadata_dir', 'output/metadata'))
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{data.get('slug', 'article')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = output_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logging.info(f"Metadata saved to: {filepath}")
        print(f"{Fore.GREEN}✓ メタデータを保存しました: {filepath}")


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(
        description='食べログから店舗情報をスクレイピングしてWordPressに投稿',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  %(prog)s https://tabelog.com/hokkaido/A0101/A010103/1067504/
  %(prog)s --config config/my_config.yaml <URL>
  %(prog)s --publish <URL>  # 公開状態で投稿
  %(prog)s --test-connection  # WordPress接続テスト
        """
    )

    parser.add_argument(
        'url',
        nargs='?',
        help='食べログのURL'
    )

    parser.add_argument(
        '--config',
        '-c',
        default='config/config.yaml',
        help='設定ファイルのパス（デフォルト: config/config.yaml）'
    )

    parser.add_argument(
        '--publish',
        '-p',
        action='store_true',
        help='下書きではなく公開状態で投稿'
    )

    parser.add_argument(
        '--test-connection',
        '-t',
        action='store_true',
        help='WordPress REST API接続テストのみ実行'
    )

    parser.add_argument(
        '--no-wordpress',
        action='store_true',
        help='WordPressに投稿せず、HTMLファイルのみ生成'
    )

    args = parser.parse_args()

    # バナー表示
    print(f"{Fore.CYAN}{Style.BRIGHT}")
    print("=" * 60)
    print("   ウマ店 WordPress自動投稿システム")
    print("   Restaurant Article Auto-Publisher")
    print("=" * 60)
    print(Style.RESET_ALL)

    # 設定を読み込み
    print(f"{Fore.YELLOW}⚙ 設定を読み込み中...")
    config = load_config(args.config)
    setup_logging(config)
    logging.info("Application started")

    # WordPress接続テスト
    if args.test_connection:
        print(f"\n{Fore.YELLOW}🔌 WordPress接続テスト中...")
        publisher = WordPressPublisher(config)
        if publisher.test_connection():
            print(f"{Fore.GREEN}✓ 接続成功!")
            sys.exit(0)
        else:
            print(f"{Fore.RED}✗ 接続失敗")
            sys.exit(1)

    # URLが指定されていない場合
    if not args.url:
        print(f"{Fore.RED}✗ URLを指定してください")
        parser.print_help()
        sys.exit(1)

    try:
        # ステップ1: スクレイピング
        print(f"\n{Fore.YELLOW}📡 ステップ1/3: 店舗情報をスクレイピング中...")
        scraper = RestaurantScraper(config)
        restaurant_data = scraper.scrape_tabelog(args.url)

        if not restaurant_data or not restaurant_data.get('name'):
            print(f"{Fore.RED}✗ スクレイピングに失敗しました")
            sys.exit(1)

        print(f"{Fore.GREEN}✓ スクレイピング完了: {restaurant_data.get('name')}")
        print(f"  - カテゴリ: {', '.join(restaurant_data.get('category', []))}")
        print(f"  - 評価: {restaurant_data.get('rating', 'N/A')}")
        print(f"  - 写真数: {len(restaurant_data.get('images', []))}")
        print(f"  - レビュー数: {len(restaurant_data.get('reviews', []))}")

        # ステップ2: 記事生成
        print(f"\n{Fore.YELLOW}✍️  ステップ2/3: Claude AIで記事を生成中...")
        generator = ArticleGenerator(config)

        # HTMLテンプレートを読み込み
        html_template = generator.load_html_template()

        article_data = generator.generate_article(restaurant_data, html_template)

        if not article_data or not article_data.get('html_content'):
            print(f"{Fore.RED}✗ 記事生成に失敗しました")
            sys.exit(1)

        print(f"{Fore.GREEN}✓ 記事生成完了")
        print(f"  - SEOタイトル: {article_data.get('seo_title')}")
        print(f"  - スラッグ: {article_data.get('slug')}")
        print(f"  - カテゴリ: {article_data.get('category')}")

        # 出力を保存
        save_output(article_data, 'html', config)
        save_output(article_data, 'metadata', config)

        # ステップ3: WordPress投稿
        if not args.no_wordpress:
            print(f"\n{Fore.YELLOW}🚀 ステップ3/3: WordPressに投稿中...")

            publisher = WordPressPublisher(config)
            status = 'publish' if args.publish else 'draft'

            post = publisher.publish_article(article_data, restaurant_data=restaurant_data, status=status)

            if post:
                print(f"{Fore.GREEN}✓ WordPress投稿完了!")
                print(f"  - 投稿ID: {post.get('id')}")
                print(f"  - ステータス: {post.get('status')}")
                print(f"  - URL: {post.get('link')}")
                print(f"\n{Fore.CYAN}👉 投稿を確認: {post.get('link')}")
            else:
                print(f"{Fore.RED}✗ WordPress投稿に失敗しました")
                sys.exit(1)
        else:
            print(f"\n{Fore.YELLOW}ℹ WordPress投稿はスキップされました")

        # 成功
        print(f"\n{Fore.GREEN}{Style.BRIGHT}{'=' * 60}")
        print(f"   ✓ すべての処理が完了しました!")
        print(f"{'=' * 60}{Style.RESET_ALL}")

        logging.info("Application finished successfully")

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}⚠ ユーザーによって中断されました")
        logging.warning("Application interrupted by user")
        sys.exit(0)

    except Exception as e:
        print(f"\n{Fore.RED}✗ エラーが発生しました: {e}")
        logging.error(f"Application error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
