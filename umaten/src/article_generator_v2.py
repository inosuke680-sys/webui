"""
記事生成モジュール v2
Claude APIでデータを生成し、HTMLテンプレートに埋め込む方式
"""

import anthropic
import json
import logging
from typing import Dict, Optional
from pathlib import Path
import re

logger = logging.getLogger(__name__)


class ArticleGenerator:
    """Claude APIを使用した記事生成クラス（v2: テンプレート埋め込み方式）"""

    def __init__(self, config: Dict):
        """
        初期化

        Args:
            config: 設定辞書
        """
        self.config = config
        self.claude_config = config.get('claude', {})
        self.api_key = self.claude_config.get('api_key')

        if not self.api_key:
            raise ValueError("Claude API key is not configured")

        self.client = anthropic.Anthropic(api_key=self.api_key)
        self.model = self.claude_config.get('model', 'claude-haiku-4-5-20251001')
        self.max_tokens = self.claude_config.get('max_tokens', 4000)  # データのみなので少なくて良い
        self.temperature = self.claude_config.get('temperature', 0.7)

    def generate_article(self, restaurant_data: Dict, html_template: str) -> Dict:
        """
        店舗データから記事を生成

        Args:
            restaurant_data: スクレイピングした店舗データ
            html_template: HTMLテンプレート（使用しない - 後方互換性のため引数保持）

        Returns:
            生成された記事データ（HTML、SEO情報など）
        """
        logger.info(f"Generating article for: {restaurant_data.get('name', 'Unknown')}")

        # Claude APIでデータ生成
        article_json = self._generate_article_data(restaurant_data)

        # HTMLテンプレートにデータを埋め込み
        html_content = self._render_html_template(article_json, restaurant_data)

        # 記事データを構築
        article_data = {
            'restaurant_name': restaurant_data.get('name', '不明'),
            'source_url': restaurant_data.get('url', ''),
            'html_content': html_content,
            'seo_title': article_json.get('seo_title', f"{restaurant_data.get('name', '不明')} | ウマ店"),
            'meta_description': article_json.get('meta_description', ''),
            'slug': article_json.get('slug', ''),
            'category': article_json.get('category', 'restaurant'),
            'tags': article_json.get('tags', []),
        }

        logger.info(f"Article generated successfully: {article_data['seo_title']}")
        return article_data

    def _generate_article_data(self, restaurant_data: Dict) -> Dict:
        """
        Claude APIでJSON形式の記事データを生成

        Args:
            restaurant_data: 店舗データ

        Returns:
            JSON形式の記事データ
        """
        prompt = f"""
以下の店舗データを元に、記事に表示するデータをJSON形式で生成してください。

【店舗データ】
{json.dumps(restaurant_data, ensure_ascii=False, indent=2)}

【出力形式】
以下のJSON形式で出力してください。JSONのみを出力し、説明文やマークダウンは不要です。

{{
  "seo_title": "SEOタイトル（60文字以内、店舗名を含む）",
  "meta_description": "メタディスクリプション（120-160文字）",
  "slug": "url-slug-format",
  "category": "カテゴリスラッグ（japanese-food, western-food, chinese-food, cafe, bar, other）",
  "tags": ["タグ1", "タグ2"],
  "rating_display": {{
    "overall": 3.5,
    "food": 3.6,
    "service": 3.5,
    "atmosphere": 3.4,
    "value": 3.7
  }},
  "hero_image": "画像URL（利用可能な場合）またはダミー画像",
  "menus": [
    {{
      "name": "メニュー名",
      "description": "メニューの説明（30文字程度）",
      "price": "¥1,000"
    }}
  ],
  "gallery_images": [
    {{
      "url": "画像URL",
      "alt": "画像の説明"
    }}
  ],
  "reviews_summary": [
    {{
      "reviewer_initial": "A",
      "reviewer_name": "匿名ユーザー",
      "date": "2024年1月",
      "rating": 4,
      "content": "レビュー内容（80文字程度に要約）"
    }}
  ],
  "access_summary": "アクセス方法の簡潔な説明"
}}

【重要な指示】
1. 実際のデータがない項目は、「不明」や空配列ではなく、適切なダミーデータを生成してください
2. メニューは最低4-6個生成してください
3. ギャラリー画像はUnsplashのダミー画像URLを使用してください
4. レビューは実データがあればそれを使用し、なければ1-2個のダミーレビューを生成してください
5. 評価は提供されたrating値を基準に、各項目を±0.2程度の範囲で調整してください
6. JSON形式のみを出力し、コードブロック記法（```）は使用しないでください
"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            response_text = response.content[0].text.strip()
            logger.info(f"Claude API stop_reason: {response.stop_reason}")

            # JSONを抽出（```json ```で囲まれている場合も考慮）
            json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)

            # JSONをパース
            article_json = json.loads(response_text)
            logger.info(f"Article data generated: {len(response_text)} characters")

            return article_json

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response text: {response_text[:500]}")
            raise
        except Exception as e:
            logger.error(f"Error generating article data: {e}")
            raise

    def _render_html_template(self, article_json: Dict, restaurant_data: Dict) -> str:
        """
        HTMLテンプレートにデータを埋め込み

        Args:
            article_json: Claude APIが生成したJSONデータ
            restaurant_data: 元の店舗データ

        Returns:
            完全なHTML文字列
        """
        # テンプレートファイルを読み込み
        template_path = Path(__file__).parent.parent / 'templates' / 'restaurant_template.html'

        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()

        # データを埋め込み
        rating = article_json.get('rating_display', {})
        menus = article_json.get('menus', [])
        gallery_images = article_json.get('gallery_images', [])
        reviews = article_json.get('reviews_summary', [])

        # 基本情報
        name = restaurant_data.get('name', '不明')
        category = restaurant_data.get('category', ['その他'])[0] if restaurant_data.get('category') else 'その他'
        area = restaurant_data.get('area', '不明')
        rating_value = restaurant_data.get('rating', 3.0)
        address = restaurant_data.get('address', '不明')
        access = restaurant_data.get('access', '不明')
        business_hours = restaurant_data.get('business_hours', '不明')
        regular_holiday = restaurant_data.get('regular_holiday', '不明')
        budget_dinner = restaurant_data.get('budget_dinner', '不明')
        budget_lunch = restaurant_data.get('budget_lunch', '不明')
        payment_methods = restaurant_data.get('payment', {})
        smoking = restaurant_data.get('smoking', '不明')
        parking = restaurant_data.get('parking', '不明')
        phone = restaurant_data.get('phone', '不明')
        source_url = restaurant_data.get('url', '#')

        # 星の表示
        stars_full = int(rating_value)
        stars_half = 1 if (rating_value - stars_full) >= 0.5 else 0
        stars_empty = 5 - stars_full - stars_half
        stars_display = '★' * stars_full + ('☆' * stars_half) + ('☆' * stars_empty)

        # ヒーロー画像
        hero_image = article_json.get('hero_image', 'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=1200&h=400&fit=crop')

        # メニューHTML生成
        menu_html = self._generate_menu_html(menus)

        # ギャラリーHTML生成
        gallery_html = self._generate_gallery_html(gallery_images)

        # レビューHTML生成
        reviews_html = self._generate_reviews_html(reviews)

        # テンプレートに値を埋め込み（プレースホルダーを使用）
        html = template.replace('{{RESTAURANT_NAME}}', name)
        html = html.replace('{{CATEGORY}}', category)
        html = html.replace('{{AREA}}', area)
        html = html.replace('{{RATING_VALUE}}', str(rating_value))
        html = html.replace('{{RATING_STARS}}', stars_display)
        html = html.replace('{{RATING_FOOD}}', str(rating.get('food', 3.5)))
        html = html.replace('{{RATING_SERVICE}}', str(rating.get('service', 3.5)))
        html = html.replace('{{RATING_ATMOSPHERE}}', str(rating.get('atmosphere', 3.5)))
        html = html.replace('{{RATING_VALUE_FOR_MONEY}}', str(rating.get('value', 3.5)))
        html = html.replace('{{ADDRESS}}', address)
        html = html.replace('{{ACCESS}}', access)
        html = html.replace('{{BUSINESS_HOURS}}', business_hours)
        html = html.replace('{{REGULAR_HOLIDAY}}', regular_holiday)
        html = html.replace('{{BUDGET_LUNCH}}', budget_lunch)
        html = html.replace('{{BUDGET_DINNER}}', budget_dinner)
        html = html.replace('{{SMOKING}}', smoking)
        html = html.replace('{{PARKING}}', parking)
        html = html.replace('{{PHONE}}', phone if phone != '不明' else '電話番号未公開')
        html = html.replace('{{SOURCE_URL}}', source_url)
        html = html.replace('{{HERO_IMAGE}}', hero_image)
        html = html.replace('{{MENU_ITEMS}}', menu_html)
        html = html.replace('{{GALLERY_IMAGES}}', gallery_html)
        html = html.replace('{{REVIEWS}}', reviews_html)

        return html

    def _generate_menu_html(self, menus: list) -> str:
        """メニューHTMLを生成"""
        if not menus:
            return '<div class="menu-item"><div class="menu-item-name">メニュー情報なし</div></div>'

        html_parts = []
        for menu in menus[:8]:  # 最大8個
            html_parts.append(f'''
                <div class="menu-item">
                    <div class="menu-item-name">{menu.get('name', '不明')}</div>
                    <div class="menu-item-description">{menu.get('description', '')}</div>
                    <div class="menu-item-price">{menu.get('price', '価格不明')}</div>
                </div>
            ''')
        return '\n'.join(html_parts)

    def _generate_gallery_html(self, images: list) -> str:
        """ギャラリーHTMLを生成"""
        if not images:
            # ダミー画像を生成
            images = [
                {"url": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=800", "alt": "店舗外観"},
                {"url": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=800", "alt": "店内雰囲気"},
                {"url": "https://images.unsplash.com/photo-1544025162-d76694265947?w=800", "alt": "料理"},
            ]

        html_parts = []
        for img in images[:8]:  # 最大8個
            url = img.get('url', '')
            alt = img.get('alt', '店舗画像')
            html_parts.append(f'''
                <div class="gallery-item" onclick="openModal('{url}')">
                    <img src="{url}?w=400&h=400&fit=crop" alt="{alt}">
                </div>
            ''')
        return '\n'.join(html_parts)

    def _generate_reviews_html(self, reviews: list) -> str:
        """レビューHTMLを生成"""
        if not reviews:
            return '<p style="text-align: center; color: #999;">レビュー情報がありません</p>'

        html_parts = []
        for review in reviews[:3]:  # 最大3個
            stars = '★' * review.get('rating', 3) + '☆' * (5 - review.get('rating', 3))
            html_parts.append(f'''
                <div class="review-card">
                    <div class="review-header">
                        <div class="reviewer-info">
                            <div class="reviewer-avatar">{review.get('reviewer_initial', 'A')}</div>
                            <div>
                                <div class="reviewer-name">{review.get('reviewer_name', '匿名')}</div>
                                <div class="review-date">{review.get('date', '最近')}</div>
                            </div>
                        </div>
                        <div class="review-rating">{stars}</div>
                    </div>
                    <div class="review-content">{review.get('content', '')}</div>
                </div>
            ''')
        return '\n'.join(html_parts)

    def load_html_template(self, template_name: str = 'restaurant_template.html') -> str:
        """
        HTMLテンプレートを読み込み（後方互換性のため）

        Args:
            template_name: テンプレートファイル名

        Returns:
            テンプレート文字列
        """
        path = Path(__file__).parent.parent / 'templates' / template_name
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            raise FileNotFoundError(f"HTMLテンプレートが見つかりません: {path}")
