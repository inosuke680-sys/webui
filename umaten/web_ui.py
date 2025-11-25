"""
Web UI for Restaurant Article Auto-Publisher
ウマ店 WordPress自動投稿システム - Web UI
"""

import os
import sys
import json
import time
import threading
import psutil
import logging
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit
import yaml

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# プロジェクトのsrcディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from scraper import RestaurantScraper
from article_generator import ArticleGenerator
from wordpress_publisher import WordPressPublisher

app = Flask(__name__)
app.config['SECRET_KEY'] = 'umaten-secret-key-2024'
socketio = SocketIO(app, cors_allowed_origins="*")

# グローバル変数
job_queue = []
job_status = {}
token_usage = {
    'minute': {'input': 0, 'output': 0, 'cost': 0, 'count': 0, 'timestamp': datetime.now()},
    'hour': {'input': 0, 'output': 0, 'cost': 0, 'count': 0, 'timestamp': datetime.now()},
    'day': {'input': 0, 'output': 0, 'cost': 0, 'count': 0, 'timestamp': datetime.now()},
    'total': {'input': 0, 'output': 0, 'cost': 0, 'count': 0}
}
settings = {
    'articles_per_hour': 10,  # デフォルト: 10記事/時間
    'auto_publish': False,  # デフォルト: 下書き保存
    'concurrent_jobs': 3,  # デフォルト: 3記事を同時並行処理
}
processing_lock = threading.Lock()
active_jobs = 0  # 現在処理中のジョブ数
executor = None  # ThreadPoolExecutor（後で初期化）


def load_config():
    """設定ファイルを読み込み"""
    config_path = Path(__file__).parent / 'config' / 'config.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def get_system_stats():
    """システム統計情報を取得"""
    return {
        'cpu_percent': psutil.cpu_percent(interval=0.1),
        'memory_percent': psutil.virtual_memory().percent,
        'memory_used_gb': round(psutil.virtual_memory().used / (1024**3), 2),
        'memory_total_gb': round(psutil.virtual_memory().total / (1024**3), 2)
    }


def reset_token_stats_if_needed():
    """時間経過に応じてトークン統計をリセット"""
    now = datetime.now()

    # 分間統計のリセット
    if (now - token_usage['minute']['timestamp']).total_seconds() >= 60:
        token_usage['minute'] = {'input': 0, 'output': 0, 'cost': 0, 'count': 0, 'timestamp': now}

    # 時間統計のリセット
    if (now - token_usage['hour']['timestamp']).total_seconds() >= 3600:
        token_usage['hour'] = {'input': 0, 'output': 0, 'cost': 0, 'count': 0, 'timestamp': now}

    # 日間統計のリセット
    if (now - token_usage['day']['timestamp']).total_seconds() >= 86400:
        token_usage['day'] = {'input': 0, 'output': 0, 'cost': 0, 'count': 0, 'timestamp': now}


def record_token_usage(input_tokens, output_tokens, cost):
    """トークン使用量を記録"""
    reset_token_stats_if_needed()

    for period in ['minute', 'hour', 'day', 'total']:
        token_usage[period]['input'] += input_tokens
        token_usage[period]['output'] += output_tokens
        token_usage[period]['cost'] += cost
        token_usage[period]['count'] += 1


def process_job(job_id, url, category_ids, config):
    """ジョブを処理"""
    global active_jobs

    try:
        job_status[job_id]['status'] = 'processing'
        job_status[job_id]['progress'] = 10
        socketio.emit('job_update', job_status[job_id])

        # ステップ1: スクレイピング
        job_status[job_id]['current_step'] = 'スクレイピング中...'
        job_status[job_id]['progress'] = 20
        socketio.emit('job_update', job_status[job_id])

        scraper = RestaurantScraper(config)
        restaurant_data = scraper.scrape_tabelog(url)

        if not restaurant_data or not restaurant_data.get('name'):
            raise Exception("店舗情報の取得に失敗しました")

        # 写真枚数チェック（ナビゲーションから取得した枚数で判定）
        photo_count = restaurant_data.get('photo_count', 0)
        if photo_count < 4:
            raise Exception(f"写真が不足しています（ナビゲーション表示: {photo_count}枚）。最低4枚必要です。")

        # 実際にスクレイピングした画像枚数もログに記録
        images = restaurant_data.get('images', [])
        logger.info(f"写真枚数 - ナビ表示: {photo_count}枚, 実際取得: {len(images)}枚")

        job_status[job_id]['progress'] = 40
        socketio.emit('job_update', job_status[job_id])

        # ステップ2: 記事生成
        job_status[job_id]['current_step'] = '記事生成中...'
        job_status[job_id]['progress'] = 50
        socketio.emit('job_update', job_status[job_id])

        article_data = None
        article_generation_failed = False
        generation_error = None

        try:
            generator = ArticleGenerator(config)
            html_template = generator.load_html_template()
            article_data = generator.generate_article(restaurant_data, html_template)

            # トークン使用量を記録
            restaurant_data_str = str(restaurant_data) if restaurant_data else ''
            html_content = article_data.get('html_content', '') if article_data else ''
            html_content_str = str(html_content) if html_content else ''

            input_tokens = len(restaurant_data_str) // 4
            output_tokens = len(html_content_str) // 4
            cost = (input_tokens / 1_000_000) * 3 + (output_tokens / 1_000_000) * 15
            record_token_usage(input_tokens, output_tokens, cost)

        except Exception as gen_error:
            # 記事生成に失敗してもカテゴリ設定のため処理を継続
            article_generation_failed = True
            generation_error = str(gen_error)
            logger.warning(f"記事生成に失敗しました: {generation_error}")
            logger.info("基本情報のみでWordPress投稿を試みます")

            # 簡易版の記事データを作成
            article_data = {
                'seo_title': restaurant_data.get('name', '不明な店舗'),
                'html_content': f"""
                    <h2>{restaurant_data.get('name', '不明な店舗')}</h2>
                    <p><strong>住所:</strong> {restaurant_data.get('address', '不明')}</p>
                    <p><strong>評価:</strong> {restaurant_data.get('rating', '不明')}</p>
                    <p><strong>カテゴリ:</strong> {', '.join(restaurant_data.get('category', [])) if isinstance(restaurant_data.get('category'), list) else restaurant_data.get('category', '不明')}</p>
                    <p><em>※ 記事生成に失敗したため、基本情報のみ掲載しています。</em></p>
                """,
                'slug': '',
                'tags': [],
                'meta_description': f"{restaurant_data.get('name', '')} - {restaurant_data.get('address', '')}"
            }

        job_status[job_id]['progress'] = 70
        socketio.emit('job_update', job_status[job_id])

        # ステップ3: WordPress投稿
        job_status[job_id]['current_step'] = 'WordPress投稿中...'
        job_status[job_id]['progress'] = 80
        socketio.emit('job_update', job_status[job_id])

        publisher = WordPressPublisher(config)
        status = 'publish' if settings['auto_publish'] else 'draft'

        # デバッグ: カテゴリIDの確認
        logger.info(f"=" * 60)
        logger.info(f"WordPress投稿準備")
        logger.info(f"  URL: {url}")
        logger.info(f"  カテゴリIDs (渡された値): {category_ids}")
        logger.info(f"  カテゴリIDs の型: {type(category_ids)}")
        if category_ids:
            logger.info(f"  カテゴリIDs の要素: {[f'{id} ({type(id)})' for id in category_ids]}")
        logger.info(f"=" * 60)

        # カテゴリIDsが指定されている場合は使用
        if category_ids and len(category_ids) > 0:
            # カテゴリIDを整数に変換（文字列の場合があるため）
            category_ids_int = []
            for cat_id in category_ids:
                try:
                    category_ids_int.append(int(cat_id))
                except (ValueError, TypeError):
                    logger.warning(f"Invalid category ID: {cat_id} (type: {type(cat_id)})")

            logger.info(f"変換後のカテゴリIDs: {category_ids_int}")

            post = publisher.create_post(
                title=article_data.get('seo_title', restaurant_data.get('name', '不明な店舗')),
                content=article_data.get('html_content', ''),
                slug=article_data.get('slug', ''),
                category_ids=category_ids_int,
                tags=article_data.get('tags', []),
                meta_description=article_data.get('meta_description'),
                seo_title=article_data.get('seo_title'),
                status=status
            )
        else:
            logger.info("カテゴリIDが指定されていないため、自動判定を使用")
            post = publisher.publish_article(article_data, restaurant_data=restaurant_data, status=status)

        if not post:
            raise Exception("WordPress投稿に失敗しました")

        job_status[job_id]['status'] = 'completed'
        job_status[job_id]['progress'] = 100

        # 記事生成失敗時は警告メッセージを追加
        if article_generation_failed:
            job_status[job_id]['current_step'] = '完了（記事生成失敗、基本情報のみ投稿）'
            job_status[job_id]['warning'] = f"記事生成に失敗しました: {generation_error}"
        else:
            job_status[job_id]['current_step'] = '完了'

        job_status[job_id]['result'] = {
            'post_id': post.get('id'),
            'post_url': post.get('link'),
            'restaurant_name': restaurant_data.get('name'),
            'article_generation_failed': article_generation_failed
        }
        socketio.emit('job_update', job_status[job_id])

    except Exception as e:
        job_status[job_id]['status'] = 'error'
        job_status[job_id]['error'] = str(e)
        socketio.emit('job_update', job_status[job_id])

    finally:
        with processing_lock:
            active_jobs -= 1


def process_queue():
    """キューを処理（バックグラウンドスレッド）"""
    global active_jobs, executor
    config = load_config()

    # ThreadPoolExecutorを大きめのmax_workersで初期化（実際の同時実行数はsettingsで制御）
    executor = ThreadPoolExecutor(max_workers=10)

    while True:
        time.sleep(0.5)

        # レート制限チェック
        articles_per_hour = settings['articles_per_hour']
        hour_count = token_usage['hour']['count']

        if hour_count >= articles_per_hour:
            # 時間制限に達した場合は待機
            continue

        # 同時実行数の上限チェック（動的に変更可能）
        concurrent_limit = settings.get('concurrent_jobs', 3)

        # キューから次のジョブを取得して並行処理
        with processing_lock:
            if job_queue and active_jobs < concurrent_limit:
                job = job_queue.pop(0)
                active_jobs += 1

                # ThreadPoolExecutorで並行処理を実行
                executor.submit(
                    process_job,
                    job['job_id'],
                    job['url'],
                    job.get('category_ids'),
                    config
                )


@app.route('/')
def index():
    """メインページ"""
    return render_template('index.html')


@app.route('/api/categories', methods=['GET'])
def get_categories():
    """WordPressカテゴリ一覧を取得"""
    try:
        config = load_config()
        publisher = WordPressPublisher(config)
        categories = publisher.get_all_categories()

        # 階層構造に整形
        category_tree = []
        category_map = {cat['id']: cat for cat in categories}

        for cat in categories:
            cat['children'] = []

        for cat in categories:
            parent_id = cat.get('parent', 0)
            if parent_id == 0:
                category_tree.append(cat)
            else:
                parent = category_map.get(parent_id)
                if parent:
                    parent['children'].append(cat)

        return jsonify({'success': True, 'categories': category_tree})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/submit', methods=['POST'])
def submit_jobs():
    """ジョブを送信"""
    try:
        data = request.json
        urls = data.get('urls', [])
        category_ids = data.get('category_ids', [])
        use_auto_category = data.get('use_auto_category', True)
        include_all_pages = data.get('include_all_pages', False)

        job_ids = []
        config = load_config()
        scraper = RestaurantScraper(config)

        for url_data in urls:
            url = url_data.get('url')
            if not url:
                continue

            # URLを正規化（サブページを削除し、重複を防ぐ）
            # ただし、リストページはそのまま
            is_list_page = '/rstLst/' in url or '/lst/' in url
            if not is_list_page:
                url = RestaurantScraper.normalize_restaurant_url(url)
                logger.info(f"Normalized URL: {url}")

            if is_list_page:
                # リストページの場合、個別URLを抽出
                logger.info(f"Detected list page: {url} (include_all_pages={include_all_pages})")
                try:
                    restaurant_urls = scraper.scrape_restaurant_list(url, include_all_pages=include_all_pages)
                    logger.info(f"Extracted {len(restaurant_urls)} URLs from list page")

                    # URL抽出が0件の場合はエラー
                    if len(restaurant_urls) == 0:
                        error_msg = f"リストページからURLを抽出できませんでした: {url}"
                        logger.error(error_msg)
                        socketio.emit('job_error', {
                            'url': url,
                            'error': error_msg
                        })
                        continue

                    # 各店舗URLをジョブとして追加
                    for restaurant_url in restaurant_urls:
                        # 重複チェック: 既にキューまたは処理中・完了したジョブに同じURLがないか確認
                        duplicate = False
                        for existing_job in job_status.values():
                            if existing_job.get('url') == restaurant_url:
                                logger.info(f"Skipping duplicate URL: {restaurant_url}")
                                duplicate = True
                                break

                        if duplicate:
                            continue

                        job_id = f"job_{int(time.time() * 1000)}_{len(job_queue)}"

                        # カテゴリIDsの決定
                        # 優先順位: 1. URL個別設定, 2. グローバル設定（手動選択時）, 3. 自動判定
                        job_category_ids = None
                        url_specific_cats = url_data.get('category_ids')

                        logger.info(f"リストページ由来のURL: {restaurant_url}")
                        logger.info(f"元のリストページURL: {url}")
                        logger.info(f"リストページに設定されたカテゴリ: {url_specific_cats}")

                        # 1. URL個別のカテゴリがある場合は最優先で使用
                        if url_specific_cats is not None and len(url_specific_cats) > 0:
                            job_category_ids = url_specific_cats
                            logger.info(f"✓ URL個別カテゴリを適用: {job_category_ids}")
                        # 2. URL個別カテゴリがなく、手動選択モードの場合はグローバルカテゴリを使用
                        elif not use_auto_category and category_ids:
                            job_category_ids = category_ids
                            logger.info(f"✓ グローバルカテゴリを適用: {job_category_ids}")
                        # 3. それ以外は自動判定（job_category_ids = None）
                        else:
                            logger.info(f"✓ カテゴリ自動判定を使用")

                        job = {
                            'job_id': job_id,
                            'url': restaurant_url,
                            'category_ids': job_category_ids
                        }

                        job_queue.append(job)

                        job_status[job_id] = {
                            'job_id': job_id,
                            'url': restaurant_url,
                            'status': 'queued',
                            'progress': 0,
                            'current_step': '待機中...',
                            'created_at': datetime.now().isoformat()
                        }

                        job_ids.append(job_id)

                except Exception as e:
                    error_msg = f"リストページ処理エラー: {url} - {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    socketio.emit('job_error', {
                        'url': url,
                        'error': error_msg
                    })
                    # リストページの抽出に失敗した場合はスキップ
                    continue
            else:
                # 通常の店舗URL
                # 重複チェック: 既にキューまたは処理中・完了したジョブに同じURLがないか確認
                duplicate = False
                for existing_job in job_status.values():
                    if existing_job.get('url') == url:
                        logger.info(f"Skipping duplicate URL: {url}")
                        duplicate = True
                        break

                if duplicate:
                    continue

                job_id = f"job_{int(time.time() * 1000)}_{len(job_queue)}"

                # カテゴリIDsの決定
                # 優先順位: 1. URL個別設定, 2. グローバル設定（手動選択時）, 3. 自動判定
                job_category_ids = None
                url_specific_cats = url_data.get('category_ids')

                # 1. URL個別のカテゴリがある場合は最優先で使用
                if url_specific_cats is not None and len(url_specific_cats) > 0:
                    job_category_ids = url_specific_cats
                    logger.info(f"URL個別カテゴリを使用: {job_category_ids}")
                # 2. URL個別カテゴリがなく、手動選択モードの場合はグローバルカテゴリを使用
                elif not use_auto_category and category_ids:
                    job_category_ids = category_ids
                    logger.info(f"グローバルカテゴリを使用: {job_category_ids}")
                # 3. それ以外は自動判定（job_category_ids = None）
                else:
                    logger.info(f"カテゴリ自動判定を使用")

                job = {
                    'job_id': job_id,
                    'url': url,
                    'category_ids': job_category_ids
                }

                job_queue.append(job)

                job_status[job_id] = {
                    'job_id': job_id,
                    'url': url,
                    'status': 'queued',
                    'progress': 0,
                    'current_step': '待機中...',
                    'created_at': datetime.now().isoformat()
                }

                job_ids.append(job_id)

        return jsonify({'success': True, 'job_ids': job_ids, 'total_jobs': len(job_ids)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/settings', methods=['GET', 'POST'])
def manage_settings():
    """設定の取得・更新"""
    if request.method == 'GET':
        return jsonify({'success': True, 'settings': settings})
    else:
        try:
            data = request.json
            settings['articles_per_hour'] = int(data.get('articles_per_hour', 10))
            settings['auto_publish'] = bool(data.get('auto_publish', False))
            settings['concurrent_jobs'] = int(data.get('concurrent_jobs', 3))
            return jsonify({'success': True, 'settings': settings})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})


@socketio.on('connect')
def handle_connect():
    """WebSocket接続"""
    print('Client connected')
    emit('connected', {'data': 'Connected'})


@socketio.on('request_stats')
def handle_stats_request():
    """統計情報のリクエスト"""
    reset_token_stats_if_needed()

    # token_usageをJSON送信可能な形式に変換（datetimeを文字列に）
    token_usage_serializable = {}
    for period, data in token_usage.items():
        token_usage_serializable[period] = {
            'input': data['input'],
            'output': data['output'],
            'cost': data['cost'],
            'count': data['count']
        }
        # timestampがある場合は文字列に変換
        if 'timestamp' in data:
            token_usage_serializable[period]['timestamp'] = data['timestamp'].isoformat()

    stats = {
        'system': get_system_stats(),
        'token_usage': token_usage_serializable,
        'queue_length': len(job_queue),
        'processing': active_jobs > 0,
        'active_jobs': active_jobs,
        'concurrent_limit': settings.get('concurrent_jobs', 3)
    }
    emit('stats_update', stats)


if __name__ == '__main__':
    # バックグラウンド処理スレッドを開始
    queue_thread = threading.Thread(target=process_queue, daemon=True)
    queue_thread.start()

    print("=" * 60)
    print("   ウマ店 WordPress自動投稿システム - Web UI")
    print("=" * 60)
    print(f"   URL: http://localhost:5000")
    print("=" * 60)

    # Flaskアプリケーションを起動
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
