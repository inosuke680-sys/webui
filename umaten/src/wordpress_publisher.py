"""
WordPress投稿モジュール
生成した記事をWordPressに自動投稿
"""

import requests
from typing import Dict, Optional
import logging
from requests.auth import HTTPBasicAuth
import json

logger = logging.getLogger(__name__)


class WordPressPublisher:
    """WordPress REST APIを使用した記事投稿クラス"""

    def __init__(self, config: Dict):
        """
        初期化

        Args:
            config: 設定辞書
        """
        self.config = config
        self.wp_config = config.get('wordpress', {})

        self.site_url = self.wp_config.get('url', '').rstrip('/')
        self.username = self.wp_config.get('username')
        self.password = self.wp_config.get('password')
        self.app_password = self.wp_config.get('app_password')

        # Basic認証設定
        self.basic_auth = self.wp_config.get('basic_auth', {})
        self.basic_auth_enabled = self.basic_auth.get('enabled', False)
        self.basic_auth_username = self.basic_auth.get('username', '')
        self.basic_auth_password = self.basic_auth.get('password', '')

        if not self.site_url:
            raise ValueError("WordPress URL is not configured")

        # Application Passwordを優先
        if self.app_password:
            # Application Passwordのスペースを除去
            self.auth_password = self.app_password.replace(' ', '')
        elif self.password:
            self.auth_password = self.password
        else:
            raise ValueError("WordPress password or app_password is not configured")

        if not self.username:
            raise ValueError("WordPress username is not configured")

        self.api_base = f"{self.site_url}/wp-json/wp/v2"
        self.auth = HTTPBasicAuth(self.username, self.auth_password)

        # セッションを作成してBasic認証を設定
        self.session = requests.Session()
        if self.basic_auth_enabled:
            logger.info("Basic authentication enabled")
            self.session.auth = HTTPBasicAuth(self.basic_auth_username, self.basic_auth_password)

        # カテゴリキャッシュ
        self.category_cache = {}
        self.all_categories_cache = None  # 全カテゴリのキャッシュ

    def get_all_categories(self) -> list:
        """
        WordPressから全カテゴリを取得（階層構造を含む）

        Returns:
            カテゴリリスト
        """
        if self.all_categories_cache is not None:
            return self.all_categories_cache

        try:
            logger.info("Fetching all categories from WordPress...")
            all_categories = []
            page = 1
            per_page = 100

            while True:
                response = self.session.get(
                    f"{self.api_base}/categories",
                    params={'per_page': per_page, 'page': page},
                    auth=self.auth,
                    timeout=10
                )

                if response.status_code == 200:
                    categories = response.json()
                    if not categories:
                        break
                    all_categories.extend(categories)
                    page += 1
                else:
                    logger.error(f"Error fetching categories: {response.status_code}")
                    break

            logger.info(f"Retrieved {len(all_categories)} categories")
            self.all_categories_cache = all_categories
            return all_categories

        except Exception as e:
            logger.error(f"Error getting all categories: {e}")
            return []

    def find_matching_categories(self, restaurant_data: Dict) -> list:
        """
        店舗データから適切なカテゴリを自動判定

        Args:
            restaurant_data: 店舗データ

        Returns:
            カテゴリIDのリスト（親カテゴリと子カテゴリの両方を含む）
        """
        logger.info("=" * 60)
        logger.info("カテゴリ自動判定開始")
        logger.info("=" * 60)

        all_categories = self.get_all_categories()
        if not all_categories:
            logger.warning("WordPressからカテゴリを取得できませんでした")
            return []

        logger.info(f"WordPress取得カテゴリ数: {len(all_categories)}")

        matched_category_ids = []

        # 住所から地域カテゴリを判定
        address = restaurant_data.get('address', '')
        area = restaurant_data.get('area', '')

        # 料理カテゴリを判定
        category_data = restaurant_data.get('category', [])
        if isinstance(category_data, str):
            category_keywords = [category_data]
        elif isinstance(category_data, list):
            category_keywords = category_data
        else:
            category_keywords = []

        name = restaurant_data.get('name', '')
        description = restaurant_data.get('description', '') or ''

        logger.info(f"店舗データ:")
        logger.info(f"  - 店名: {name}")
        logger.info(f"  - 住所: {address}")
        logger.info(f"  - エリア: {area}")
        logger.info(f"  - カテゴリキーワード: {category_keywords}")
        logger.info(f"  - 説明: {description[:100] if description else 'なし'}")

        # 地域カテゴリのマッチング（全国対応）
        region_matches = []

        logger.info(f"地域検索開始...")

        # 住所から都道府県を検出
        detected_prefecture = None
        prefecture_keywords = {
            '北海道': '北海道',
            '青森県': '青森',
            '岩手県': '岩手',
            '宮城県': '宮城',
            '秋田県': '秋田',
            '山形県': '山形',
            '福島県': '福島',
            '茨城県': '茨城',
            '栃木県': '栃木',
            '群馬県': '群馬',
            '埼玉県': '埼玉',
            '千葉県': '千葉',
            '東京都': '東京',
            '神奈川県': '神奈川',
            '新潟県': '新潟',
            '富山県': '富山',
            '石川県': '石川',
            '福井県': '福井',
            '山梨県': '山梨',
            '長野県': '長野',
            '岐阜県': '岐阜',
            '静岡県': '静岡',
            '愛知県': '愛知',
            '三重県': '三重',
            '滋賀県': '滋賀',
            '京都府': '京都',
            '大阪府': '大阪',
            '兵庫県': '兵庫',
            '奈良県': '奈良',
            '和歌山県': '和歌山',
            '鳥取県': '鳥取',
            '島根県': '島根',
            '岡山県': '岡山',
            '広島県': '広島',
            '山口県': '山口',
            '徳島県': '徳島',
            '香川県': '香川',
            '愛媛県': '愛媛',
            '高知県': '高知',
            '福岡県': '福岡',
            '佐賀県': '佐賀',
            '長崎県': '長崎',
            '熊本県': '熊本',
            '大分県': '大分',
            '宮崎県': '宮崎',
            '鹿児島県': '鹿児島',
            '沖縄県': '沖縄',
        }

        for pref_full, pref_short in prefecture_keywords.items():
            if pref_full in address or pref_short in address:
                detected_prefecture = pref_short
                logger.info(f"  住所から都道府県「{pref_full}」を検出")
                break

        # 都道府県カテゴリを探す
        prefecture_cat = None
        if detected_prefecture:
            for cat in all_categories:
                cat_name = cat.get('name', '')
                cat_slug = cat.get('slug', '')
                # 都道府県カテゴリ（親が0）で、名前に都道府県名が含まれる
                if cat.get('parent', 0) == 0 and detected_prefecture in cat_name:
                    prefecture_cat = cat
                    logger.info(f"  ✓ 都道府県カテゴリ: {cat_name} (ID: {cat['id']}, slug: {cat_slug})")
                    break

        # 市区町村カテゴリを探す
        # 住所から市区町村名を抽出
        import re
        city_pattern = r'([^\s]+?[市区町村])'
        city_matches_in_address = re.findall(city_pattern, address)

        if city_matches_in_address:
            logger.info(f"  住所から市区町村候補を抽出: {city_matches_in_address}")

            # WordPressカテゴリから市区町村を探す
            if prefecture_cat:
                prefecture_id = prefecture_cat.get('id')
                for city_keyword in city_matches_in_address:
                    # 「市」「町」「村」「区」を除いた部分
                    city_base = city_keyword.rstrip('市区町村')

                    for cat in all_categories:
                        cat_name = cat.get('name', '')
                        cat_parent = cat.get('parent', 0)

                        # 親カテゴリが都道府県で、名前に市区町村名が含まれる
                        if cat_parent == prefecture_id and (city_base in cat_name or city_keyword in cat_name):
                            region_matches.append(cat)
                            logger.info(f"  ✓ 市区町村カテゴリ: {cat_name} (ID: {cat['id']}, parent: {cat_parent})")
                            break  # 最初にマッチしたものを使用

        # 料理ジャンル（店舗カテゴリ）のマッチング
        genre_matches = []
        logger.info(f"料理ジャンル検索開始...")

        if category_keywords:
            logger.info(f"  店舗カテゴリキーワード: {category_keywords}")

            # 料理ジャンルの親カテゴリを探す（「ジャンル」「料理」などの名前）
            genre_parent_cat = None
            for cat in all_categories:
                cat_name = cat.get('name', '')
                # 親が0で「ジャンル」や「料理」を含むカテゴリを探す
                if cat.get('parent', 0) == 0 and ('ジャンル' in cat_name or '料理' in cat_name or 'グルメ' in cat_name):
                    genre_parent_cat = cat
                    logger.info(f"  料理ジャンル親カテゴリ: {cat_name} (ID: {cat['id']})")
                    break

            # 料理ジャンルのマッチング
            for keyword in category_keywords:
                keyword_lower = keyword.lower() if keyword else ''
                keyword_clean = keyword.replace('・', '').replace(' ', '')  # 記号除去

                for cat in all_categories:
                    cat_name = cat.get('name', '')
                    cat_parent = cat.get('parent', 0)

                    # 料理ジャンル親カテゴリの子、または親が0のカテゴリ
                    is_genre_child = genre_parent_cat and cat_parent == genre_parent_cat.get('id')
                    is_top_level = cat_parent == 0

                    if is_genre_child or (is_top_level and cat not in [prefecture_cat] if prefecture_cat else True):
                        # カテゴリ名との部分一致チェック
                        if (keyword in cat_name or
                            keyword_clean in cat_name.replace('・', '').replace(' ', '') or
                            cat_name in keyword or
                            # よくあるジャンル名のマッピング
                            (keyword in ['居酒屋', 'いざかや'] and '居酒屋' in cat_name) or
                            (keyword in ['寿司', 'すし', 'スシ'] and '寿司' in cat_name) or
                            (keyword in ['ラーメン', 'らーめん'] and 'ラーメン' in cat_name) or
                            (keyword in ['焼肉', 'やきにく'] and '焼肉' in cat_name) or
                            (keyword in ['焼き鳥', 'やきとり', '焼鳥'] and '焼き鳥' in cat_name) or
                            (keyword in ['イタリアン', 'イタリア料理'] and 'イタリア' in cat_name) or
                            (keyword in ['フレンチ', 'フランス料理'] and ('フレンチ' in cat_name or 'フランス' in cat_name)) or
                            (keyword in ['中華', '中国料理'] and '中華' in cat_name) or
                            (keyword in ['カフェ', 'cafe', 'Cafe'] and 'カフェ' in cat_name)):

                            genre_matches.append(cat)
                            logger.info(f"  ✓ 料理ジャンルカテゴリ: {cat_name} (ID: {cat['id']}, parent: {cat_parent})")
                            break  # 各キーワードで最初にマッチしたものを使用

        # カテゴリIDを収集（親カテゴリも含める）
        def add_category_with_parents(category):
            """カテゴリとその親カテゴリをすべて追加"""
            if category['id'] not in matched_category_ids:
                matched_category_ids.append(category['id'])
                logger.info(f"カテゴリ追加: {category['name']} (ID: {category['id']})")

            # 親カテゴリがあれば再帰的に追加
            parent_id = category.get('parent', 0)
            if parent_id > 0:
                parent_cat = next((c for c in all_categories if c['id'] == parent_id), None)
                if parent_cat:
                    add_category_with_parents(parent_cat)

        # 地域カテゴリを追加
        logger.info("=" * 60)
        logger.info(f"地域カテゴリマッチ数: {len(region_matches)}")
        for cat in region_matches[:1]:  # 最初の1つのみ
            add_category_with_parents(cat)

        # 料理ジャンルカテゴリを追加
        logger.info("=" * 60)
        logger.info(f"料理ジャンルカテゴリマッチ数: {len(genre_matches)}")
        for cat in genre_matches[:2]:  # 最初の2つまで
            add_category_with_parents(cat)

        logger.info("=" * 60)
        if matched_category_ids:
            logger.info(f"✓ 最終的に選択されたカテゴリID: {matched_category_ids}")
            # 選択されたカテゴリ名を表示
            selected_cat_names = [c.get('name') for c in all_categories if c.get('id') in matched_category_ids]
            logger.info(f"✓ カテゴリ名: {selected_cat_names}")
        else:
            logger.warning("✗ カテゴリが1つも選択されませんでした")
        logger.info("=" * 60)

        return matched_category_ids

    def test_connection(self) -> bool:
        """
        WordPress REST API接続テスト

        Returns:
            接続成功したかどうか
        """
        try:
            logger.info("Testing WordPress connection...")
            response = self.session.get(
                f"{self.api_base}/users/me",
                auth=self.auth,
                timeout=10
            )

            if response.status_code == 200:
                user_data = response.json()
                logger.info(f"Connection successful! Logged in as: {user_data.get('name')}")
                return True
            else:
                logger.error(f"Connection failed: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"Connection error: {e}")
            return False

    def get_category_id(self, category_slug: str) -> Optional[int]:
        """
        カテゴリスラッグからカテゴリIDを取得

        Args:
            category_slug: カテゴリスラッグ

        Returns:
            カテゴリID（存在しない場合はNone）
        """
        # キャッシュをチェック
        if category_slug in self.category_cache:
            return self.category_cache[category_slug]

        try:
            logger.info(f"Fetching category ID for slug: {category_slug}")
            response = self.session.get(
                f"{self.api_base}/categories",
                params={'slug': category_slug},
                auth=self.auth,
                timeout=10
            )

            if response.status_code == 200:
                categories = response.json()
                if categories:
                    category_id = categories[0]['id']
                    self.category_cache[category_slug] = category_id
                    logger.info(f"Found category ID: {category_id}")
                    return category_id
                else:
                    logger.warning(f"Category not found: {category_slug}")
                    return None
            else:
                logger.error(f"Error fetching category: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error getting category ID: {e}")
            return None

    def create_post(
        self,
        title: str,
        content: str,
        slug: str,
        category_ids: Optional[list] = None,
        tags: Optional[list] = None,
        meta_description: Optional[str] = None,
        seo_title: Optional[str] = None,
        status: str = 'draft',
        featured_image_url: Optional[str] = None
    ) -> Optional[Dict]:
        """
        WordPress投稿を作成

        Args:
            title: 投稿タイトル
            content: 投稿コンテンツ（HTML）
            slug: 投稿スラッグ
            category_ids: カテゴリIDのリスト
            tags: タグリスト
            meta_description: メタディスクリプション
            status: 投稿ステータス（draft/publish）
            featured_image_url: アイキャッチ画像URL

        Returns:
            作成された投稿データ
        """
        try:
            logger.info(f"Creating WordPress post: {title}")

            # コンテンツをカスタムHTMLブロック形式でラップ
            # WordPressのGutenbergブロックエディタでは、カスタムHTMLは特別な形式が必要
            gutenberg_content = f"""<!-- wp:html -->
{content}
<!-- /wp:html -->"""

            # 投稿データを構築
            post_data = {
                'title': title,
                'content': gutenberg_content,
                'slug': slug,
                'status': status,
                'format': 'standard',
            }

            # カテゴリを設定
            if category_ids and len(category_ids) > 0:
                # カテゴリIDが整数であることを確認
                category_ids_int = []
                for cat_id in category_ids:
                    try:
                        category_ids_int.append(int(cat_id))
                    except (ValueError, TypeError) as e:
                        logger.error(f"カテゴリID変換エラー: {cat_id} ({type(cat_id)}) - {e}")

                post_data['categories'] = category_ids_int
                logger.info(f"=" * 60)
                logger.info(f"カテゴリ設定")
                logger.info(f"  元のカテゴリIDs: {category_ids}")
                logger.info(f"  変換後のカテゴリIDs: {category_ids_int}")
                logger.info(f"=" * 60)
            else:
                logger.warning("カテゴリIDが空です。未分類になる可能性があります。")

            # タグを設定（タグIDではなくタグ名を使用する場合）
            if tags:
                # タグIDを取得または作成
                tag_ids = self._get_or_create_tags(tags)
                if tag_ids:
                    post_data['tags'] = tag_ids

            # SEO情報を複数のプラグイン形式で設定
            meta_fields = {}

            # Yoast SEO対応（SEO専用タイトルを使用）
            if meta_description:
                meta_fields['_yoast_wpseo_metadesc'] = meta_description
            if seo_title:
                meta_fields['_yoast_wpseo_title'] = seo_title

            # SEO SIMPLE PACK (SSP) 対応（投稿タイトルをそのまま使用）
            if title:
                meta_fields['ssp_meta_title'] = title
            if meta_description:
                meta_fields['ssp_meta_description'] = meta_description

            # All in One SEO Pack対応（SEO専用タイトルを使用）
            if meta_description:
                meta_fields['_aioseop_description'] = meta_description
            if seo_title:
                meta_fields['_aioseop_title'] = seo_title

            if meta_fields:
                post_data['meta'] = meta_fields
                logger.info(f"SEO meta fields set: {list(meta_fields.keys())}")

            # デバッグ: WordPress APIに送信するデータを確認
            logger.info(f"=" * 60)
            logger.info(f"WordPress REST APIリクエストデータ:")
            logger.info(f"  Title: {post_data.get('title')}")
            logger.info(f"  Slug: {post_data.get('slug')}")
            logger.info(f"  Status: {post_data.get('status')}")
            logger.info(f"  Categories: {post_data.get('categories', 'なし')}")
            logger.info(f"  Tags: {post_data.get('tags', 'なし')}")
            logger.info(f"=" * 60)

            # 投稿を作成
            response = self.session.post(
                f"{self.api_base}/posts",
                json=post_data,
                auth=self.auth,
                timeout=30
            )

            if response.status_code == 201:
                post = response.json()
                logger.info(f"=" * 60)
                logger.info(f"投稿作成成功!")
                logger.info(f"  投稿ID: {post['id']}")
                logger.info(f"  URL: {post['link']}")
                logger.info(f"  実際に設定されたカテゴリIDs: {post.get('categories', [])}")
                logger.info(f"=" * 60)

                # SEO SIMPLE PACK用のmeta情報が正しく設定されたか確認
                if meta_fields:
                    post_id = post['id']
                    self._verify_and_update_seo_meta(post_id, title, meta_description)

                return post
            else:
                logger.error(f"=" * 60)
                logger.error(f"投稿作成失敗!")
                logger.error(f"  HTTPステータス: {response.status_code}")
                logger.error(f"  エラーレスポンス: {response.text}")
                logger.error(f"  送信したカテゴリIDs: {post_data.get('categories', 'なし')}")
                logger.error(f"=" * 60)
                return None

        except Exception as e:
            logger.error(f"=" * 60)
            logger.error(f"投稿作成時の例外エラー: {e}")
            logger.error(f"=" * 60)
            import traceback
            traceback.print_exc()
            return None

    def update_post(
        self,
        post_id: int,
        title: Optional[str] = None,
        content: Optional[str] = None,
        status: Optional[str] = None
    ) -> Optional[Dict]:
        """
        既存の投稿を更新

        Args:
            post_id: 投稿ID
            title: 新しいタイトル
            content: 新しいコンテンツ
            status: 新しいステータス

        Returns:
            更新された投稿データ
        """
        try:
            logger.info(f"Updating post ID: {post_id}")

            post_data = {}
            if title:
                post_data['title'] = title
            if content:
                post_data['content'] = content
            if status:
                post_data['status'] = status

            response = self.session.post(
                f"{self.api_base}/posts/{post_id}",
                json=post_data,
                auth=self.auth,
                timeout=30
            )

            if response.status_code == 200:
                post = response.json()
                logger.info(f"Post updated successfully! ID: {post['id']}")
                return post
            else:
                logger.error(f"Error updating post: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"Error updating post: {e}")
            return None

    def _get_or_create_tags(self, tag_names: list) -> list:
        """
        タグIDを取得または作成

        Args:
            tag_names: タグ名のリスト

        Returns:
            タグIDのリスト
        """
        tag_ids = []

        for tag_name in tag_names:
            try:
                # 既存のタグを検索
                response = self.session.get(
                    f"{self.api_base}/tags",
                    params={'search': tag_name},
                    auth=self.auth,
                    timeout=10
                )

                if response.status_code == 200:
                    tags = response.json()
                    if tags:
                        # 完全一致するタグを探す
                        for tag in tags:
                            if tag['name'].lower() == tag_name.lower():
                                tag_ids.append(tag['id'])
                                break
                        else:
                            # 見つからない場合は新規作成
                            new_tag_id = self._create_tag(tag_name)
                            if new_tag_id:
                                tag_ids.append(new_tag_id)
                    else:
                        # タグが存在しない場合は作成
                        new_tag_id = self._create_tag(tag_name)
                        if new_tag_id:
                            tag_ids.append(new_tag_id)

            except Exception as e:
                logger.error(f"Error getting/creating tag '{tag_name}': {e}")

        return tag_ids

    def _create_tag(self, tag_name: str) -> Optional[int]:
        """
        新しいタグを作成

        Args:
            tag_name: タグ名

        Returns:
            作成されたタグID
        """
        try:
            response = self.session.post(
                f"{self.api_base}/tags",
                json={'name': tag_name},
                auth=self.auth,
                timeout=10
            )

            if response.status_code == 201:
                tag = response.json()
                logger.info(f"Created new tag: {tag_name} (ID: {tag['id']})")
                return tag['id']
            else:
                logger.error(f"Error creating tag: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Error creating tag: {e}")
            return None

    def _verify_and_update_seo_meta(self, post_id: int, post_title: Optional[str], meta_description: Optional[str]) -> bool:
        """
        SEO SIMPLE PACKのmeta情報が正しく設定されたか確認し、必要に応じて更新

        Args:
            post_id: 投稿ID
            post_title: 投稿タイトル（WPエディタのタイトルと同じ）
            meta_description: メタディスクリプション

        Returns:
            成功したかどうか
        """
        try:
            # 投稿のmeta情報を取得
            logger.info(f"投稿 {post_id} のSEO meta情報を確認中...")
            response = self.session.get(
                f"{self.api_base}/posts/{post_id}",
                params={'context': 'edit'},
                auth=self.auth,
                timeout=10
            )

            if response.status_code != 200:
                logger.warning(f"投稿情報の取得に失敗: {response.status_code}")
                return False

            post = response.json()
            current_meta = post.get('meta', {})

            # SEO SIMPLE PACK用のmeta情報を確認
            needs_update = False
            update_meta = {}

            if post_title:
                if current_meta.get('ssp_meta_title') != post_title:
                    logger.warning(f"ssp_meta_title が設定されていません。更新します: {post_title}")
                    update_meta['ssp_meta_title'] = post_title
                    needs_update = True
                else:
                    logger.info(f"✓ ssp_meta_title 設定確認: {post_title}")

            if meta_description:
                if current_meta.get('ssp_meta_description') != meta_description:
                    logger.warning(f"ssp_meta_description が設定されていません。更新します")
                    update_meta['ssp_meta_description'] = meta_description
                    needs_update = True
                else:
                    logger.info(f"✓ ssp_meta_description 設定確認")

            # 必要に応じてmeta情報を更新
            if needs_update:
                logger.info(f"SEO meta情報を更新中: {list(update_meta.keys())}")
                update_response = self.session.post(
                    f"{self.api_base}/posts/{post_id}",
                    json={'meta': update_meta},
                    auth=self.auth,
                    timeout=30
                )

                if update_response.status_code == 200:
                    logger.info("✓ SEO meta情報の更新に成功しました")
                    return True
                else:
                    logger.error(f"SEO meta情報の更新に失敗: {update_response.status_code} - {update_response.text}")
                    return False
            else:
                logger.info("SEO meta情報は既に正しく設定されています")
                return True

        except Exception as e:
            logger.error(f"SEO meta情報の確認・更新中にエラー: {e}")
            return False

    def _set_featured_image(self, post_id: int, image_url: str) -> bool:
        """
        アイキャッチ画像を設定

        Args:
            post_id: 投稿ID
            image_url: 画像URL

        Returns:
            設定成功したかどうか
        """
        try:
            logger.info(f"Setting featured image for post {post_id}: {image_url}")

            # 画像をダウンロード
            img_response = self.session.get(image_url, timeout=30)
            if img_response.status_code != 200:
                logger.error(f"Failed to download image: {img_response.status_code}")
                return False

            # ファイル名を取得
            import os
            from urllib.parse import urlparse
            filename = os.path.basename(urlparse(image_url).path)
            if not filename:
                filename = 'featured-image.jpg'

            # メディアをアップロード
            files = {
                'file': (filename, img_response.content, img_response.headers.get('content-type', 'image/jpeg'))
            }

            headers = {
                'Content-Disposition': f'attachment; filename="{filename}"'
            }

            media_response = self.session.post(
                f"{self.api_base}/media",
                files=files,
                headers=headers,
                auth=self.auth,
                timeout=60
            )

            if media_response.status_code == 201:
                media = media_response.json()
                media_id = media['id']

                # 投稿にアイキャッチ画像を設定
                post_response = self.session.post(
                    f"{self.api_base}/posts/{post_id}",
                    json={'featured_media': media_id},
                    auth=self.auth,
                    timeout=30
                )

                if post_response.status_code == 200:
                    logger.info(f"Featured image set successfully! Media ID: {media_id}")
                    return True
                else:
                    logger.error(f"Error setting featured image: {post_response.status_code}")
                    return False
            else:
                logger.error(f"Error uploading media: {media_response.status_code}")
                return False

        except Exception as e:
            logger.error(f"Error setting featured image: {e}")
            return False

    def publish_article(self, article_data: Dict, restaurant_data: Dict = None, status: str = 'draft') -> Optional[Dict]:
        """
        記事データを投稿

        Args:
            article_data: 記事データ（article_generatorから生成されたもの）
            restaurant_data: 店舗データ（スクレイピングされたもの）
            status: 投稿ステータス（draft/publish）

        Returns:
            作成された投稿データ
        """
        # カテゴリを自動判定
        category_ids = []
        if restaurant_data:
            category_ids = self.find_matching_categories(restaurant_data)

        # カテゴリが見つからない場合、デフォルトカテゴリを使用
        if not category_ids:
            logger.warning("No matching categories found, trying default category")
            # デフォルトカテゴリ「未分類」を試す
            default_cat = self.get_category_id('uncategorized')
            if default_cat:
                category_ids = [default_cat]

        return self.create_post(
            title=article_data.get('seo_title', article_data.get('restaurant_name', '不明な店舗')),
            content=article_data.get('html_content', ''),
            slug=article_data.get('slug', ''),
            category_ids=category_ids,
            tags=article_data.get('tags', []),
            meta_description=article_data.get('meta_description'),
            seo_title=article_data.get('seo_title'),
            status=status
        )
