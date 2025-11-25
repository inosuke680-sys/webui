"""
記事生成モジュール v2
Claude APIでデータを生成し、HTMLテンプレートに埋め込む方式
"""

import anthropic
import json
import logging
import time
from typing import Dict, Optional
from pathlib import Path
import re
import sys

# _html_builderをインポート（絶対インポート）
sys.path.insert(0, str(Path(__file__).parent))
from _html_builder import build_complete_html

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
        self.max_tokens = self.claude_config.get('max_tokens', 4000)  # 詳細分析のために4000に拡張
        self.temperature = self.claude_config.get('temperature', 0.7)

        # 使用するモデルをログ出力
        logger.info(f"🤖 使用モデル: {self.model}")
        logger.info(f"📊 最大トークン数: {self.max_tokens}")

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
        # データを最小化してトークン数を削減
        # カテゴリの安全な取得
        category_raw = restaurant_data.get('category')
        if isinstance(category_raw, list) and len(category_raw) > 0:
            category_display = category_raw[0]
        elif isinstance(category_raw, str) and category_raw:
            category_display = category_raw
        else:
            category_display = 'グルメ'

        compact_data = {
            "name": restaurant_data.get('name'),
            "category": category_display,
            "rating": restaurant_data.get('rating'),
            "address": restaurant_data.get('address'),
            "area": restaurant_data.get('area') or '',
            "budget": restaurant_data.get('budget'),
            "hours": restaurant_data.get('business_hours'),
        }

        # プロンプト（SEO強化＆著作権配慮＆トークン効率化版）
        prompt = f"""店舗データからSEO最適化された記事データをJSON形式で生成してください。

【店舗データ】
{json.dumps(compact_data, ensure_ascii=False)}

【著作権・独自性に関する重要指示】
- 他サイトのレビューをコピーせず、店舗の特徴から独自の視点で魅力を表現
- 事実情報（住所・価格等）以外は必ずオリジナルの文章で作成
- 「〜と評判」「口コミで人気」等の表現で独自分析として記述

【SEO最適化指示】
- タイトル：「{compact_data.get('name')} | {compact_data.get('area')}の{category_display}」形式
- 検索意図：「地域名+料理ジャンル」「店名+口コミ」「店名+メニュー」を意識
- meta_description：店舗の魅力→具体的情報→行動喚起の構成

【文章スタイル - 重要】
- 読者が行きたくなる感情的価値を伝える
- 具体的なシーン提案（デート、家族連れ、一人飲み等）
- 語尾は必ず多様化すること。「〜ます」の連続禁止
  良い例：「〜でしょう」「〜かもしれません」「〜ですね」「〜のが特徴」「〜と言えます」「〜が魅力」「〜がおすすめ」
- 体言止めも適度に使用（例：「絶品の炭火焼き」「落ち着いた雰囲気」）

【出力JSON】JSONのみ出力。説明文不要。
{{"seo_title":"60字以内","meta_description":"120-160字","slug":"english-slug","category":"japanese-food/western-food/chinese-food/cafe/bar/other","tags":["タグ1","タグ2"],"rating_display":{{"overall":3.5,"food":3.6,"service":3.5,"atmosphere":3.4,"value":3.7}},"menus":[{{"name":"名","description":"30字","price":"¥1000"}}],"reviews_summary":[{{"reviewer_initial":"A","date":"2024/01","rating":4,"content":"独自視点の80字評価文"}}],"detailed_analysis":{{"sections":[{{"heading":"見出し","content":"150-200字の独自分析"}}]}},"recommendation":{{"content":"150字のおすすめポイント"}},"seo_text":"150字のSEO文"}}

【生成量】menus:3個, reviews_summary:3個, detailed_analysis.sections:4個
【評価】rating値を基準に各項目±0.2で調整"""

        # レート制限対策：リトライロジックを実装
        max_retries = 5
        retry_count = 0
        base_delay = 10  # 基本待機時間（秒）

        while retry_count < max_retries:
            try:
                logger.info(f"🚀 Claude API呼び出し - モデル: {self.model}, 最大トークン: {self.max_tokens}")
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

                # トークン使用量とコストをログ出力
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens

                # Haiku 4.5の料金: Input $1/MTok, Output $5/MTok
                input_cost = (input_tokens / 1_000_000) * 1
                output_cost = (output_tokens / 1_000_000) * 5
                total_cost = input_cost + output_cost

                logger.info(f"トークン使用量 - Input: {input_tokens}, Output: {output_tokens}")
                logger.info(f"API費用 - Input: ${input_cost:.4f}, Output: ${output_cost:.4f}, 合計: ${total_cost:.4f}")
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
                logger.error(f"Response text: {response_text[:500] if 'response_text' in locals() else 'No response'}")
                raise
            except Exception as e:
                error_str = str(e)
                if '429' in error_str or 'rate_limit' in error_str.lower():
                    retry_count += 1
                    if retry_count >= max_retries:
                        logger.error(f"レート制限エラー: 最大リトライ回数（{max_retries}）に達しました")
                        raise Exception(f"API レート制限エラー: {max_retries}回リトライしましたが失敗しました。しばらく待ってから再試行してください。")

                    # 指数バックオフで待機時間を計算
                    wait_time = base_delay * (2 ** (retry_count - 1))
                    logger.warning(f"レート制限エラー発生。{wait_time}秒待機してリトライします（{retry_count}/{max_retries}）...")

                    time.sleep(wait_time)
                else:
                    # レート制限以外のエラーはそのまま再スロー
                    logger.error(f"Error generating article data: {e}")
                    raise

        # max_retriesに達した場合（通常はここには到達しない）
        raise Exception("API呼び出しが予期せず失敗しました")

    def _render_html_template(self, article_json: Dict, restaurant_data: Dict) -> str:
        """
        HTMLテンプレートにデータを埋め込み

        Args:
            article_json: Claude APIが生成したJSONデータ
            restaurant_data: 元の店舗データ

        Returns:
            完全なHTML文字列
        """
        # データを抽出
        rating = article_json.get('rating_display', {})
        menus = article_json.get('menus', [])
        reviews = article_json.get('reviews_summary', [])

        # 画像は実際にスクレイピングしたデータを使用（Claude APIからではない）
        scraped_images = restaurant_data.get('images', [])
        gallery_images = [{"url": img, "alt": f"{restaurant_data.get('name', '店舗')}の写真"} for img in scraped_images[:12]]  # 最大12枚

        # 基本情報
        name = restaurant_data.get('name', '不明')
        # カテゴリの処理：配列の場合は最初の要素、空の場合は「その他」
        category_list = restaurant_data.get('category', [])
        if category_list and isinstance(category_list, list) and len(category_list) > 0:
            category = category_list[0]
        elif isinstance(category_list, str) and category_list:
            category = category_list
        else:
            category = 'その他'
        area = restaurant_data.get('area', '不明')
        rating_value = float(restaurant_data.get('rating', 3.0)) if restaurant_data.get('rating') else rating.get('overall', 3.5)
        address = restaurant_data.get('address', '不明')

        # アクセス情報の処理（不明の場合は住所から推測）
        access_raw = restaurant_data.get('access')
        station_raw = restaurant_data.get('station')
        if access_raw and access_raw != '不明':
            access = access_raw
        elif station_raw and station_raw != '不明':
            access = f"{station_raw}より徒歩圏内"
        elif address and address != '不明':
            # 住所から推測（簡易的）
            access = f"{address.split('市')[0]}市内" if '市' in address else "公共交通機関をご利用ください"
        else:
            access = "詳細はお店にお問い合わせください"

        # 営業時間・定休日の処理
        business_hours_raw = restaurant_data.get('business_hours')
        if business_hours_raw and business_hours_raw != '不明' and business_hours_raw.strip():
            business_hours = business_hours_raw
        else:
            business_hours = "11:00-22:00（営業時間はお店にご確認ください）"

        regular_holiday_raw = restaurant_data.get('regular_holiday') or restaurant_data.get('holiday')
        if regular_holiday_raw and regular_holiday_raw != '不明' and regular_holiday_raw.strip():
            regular_holiday = regular_holiday_raw
        else:
            regular_holiday = "不定休（詳細はお店にご確認ください）"

        # 予算の処理
        budget_dinner_raw = restaurant_data.get('budget_dinner') or restaurant_data.get('budget', {}).get('dinner')
        budget_lunch_raw = restaurant_data.get('budget_lunch') or restaurant_data.get('budget', {}).get('lunch')

        if budget_dinner_raw and budget_dinner_raw != '不明' and str(budget_dinner_raw).strip():
            budget_dinner = budget_dinner_raw
        else:
            budget_dinner = "¥1,000-¥3,000"

        if budget_lunch_raw and budget_lunch_raw != '不明' and str(budget_lunch_raw).strip():
            budget_lunch = budget_lunch_raw
        else:
            budget_lunch = "¥800-¥1,500"

        # 喫煙・駐車場の処理
        smoking_raw = restaurant_data.get('smoking')
        if smoking_raw and smoking_raw != '不明' and smoking_raw.strip():
            smoking = smoking_raw
        else:
            smoking = "全席禁煙"  # デフォルトは全席禁煙

        parking_raw = restaurant_data.get('parking')
        if parking_raw and parking_raw != '不明' and parking_raw.strip():
            parking = parking_raw
        else:
            parking = "近隣にコインパーキングあり"

        phone = restaurant_data.get('phone', '')
        if not phone or phone == '不明':
            phone = "電話番号未公開"

        source_url = restaurant_data.get('url', '#')
        official_website = restaurant_data.get('official_website', '')

        # 星の表示
        stars_full = int(rating_value)
        stars_half = 1 if (rating_value - stars_full) >= 0.5 else 0
        stars_empty = 5 - stars_full - stars_half
        stars_display = '★' * stars_full + ('☆' if stars_half else '') + ('☆' * (stars_empty - stars_half))

        # ヒーロー画像：実際にスクレイピングした最初の画像を使用
        if scraped_images:
            hero_image = scraped_images[0]
        else:
            # 画像がない場合のみダミー画像を使用
            hero_image = 'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=1200&h=400&fit=crop'

        # 評価パーセンテージ計算
        rating_food = rating.get('food', 3.5)
        rating_service = rating.get('service', 3.5)
        rating_atmosphere = rating.get('atmosphere', 3.4)
        rating_value_money = rating.get('value', 3.7)

        # メニューHTML生成
        menu_html = self._generate_menu_html(menus)

        # ギャラリーHTML生成
        gallery_html = self._generate_gallery_html(gallery_images)

        # レビューHTML生成
        reviews_html = self._generate_reviews_html(reviews)

        # 詳細分析セクションのHTML生成
        detailed_analysis = article_json.get('detailed_analysis', {})
        detailed_analysis_html = self._generate_detailed_analysis_html(detailed_analysis)

        # おすすめポイントHTML生成
        recommendation = article_json.get('recommendation', {})
        recommendation_html = self._generate_recommendation_html(recommendation)

        # SEOテキスト取得
        seo_text = article_json.get('seo_text', f"{name}の詳細情報をご紹介します。")

        # 完全なHTMLを構築
        html = self._get_html_template(
            name=name,
            category=category,
            area=area,
            rating_value=rating_value,
            stars_display=stars_display,
            rating_food=rating_food,
            rating_service=rating_service,
            rating_atmosphere=rating_atmosphere,
            rating_value_money=rating_value_money,
            address=address,
            access=access,
            business_hours=business_hours,
            regular_holiday=regular_holiday,
            budget_lunch=budget_lunch,
            budget_dinner=budget_dinner,
            smoking=smoking,
            parking=parking,
            phone=phone,
            source_url=source_url,
            official_website=official_website,
            hero_image=hero_image,
            menu_html=menu_html,
            gallery_html=gallery_html,
            reviews_html=reviews_html,
            detailed_analysis_html=detailed_analysis_html,
            recommendation_html=recommendation_html,
            seo_text=seo_text
        )

        return html

    def _generate_menu_html(self, menus: list) -> str:
        """メニューHTMLを生成"""
        if not menus:
            return '<div class="menu-item"><div class="menu-item-name">メニュー情報なし</div></div>'

        html_parts = []
        for menu in menus[:6]:  # 最大6個（コスト削減のため8→6に削減）
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
            # 画像がない場合のメッセージ
            return '<p style="text-align: center; color: #999;">画像情報がありません</p>'

        html_parts = []
        for img in images[:12]:  # 最大12個
            url = img.get('url', '')
            alt = img.get('alt', '店舗画像')

            # サムネイルURLを生成（食べログの画像URLの場合、既に適切なサイズになっている）
            # Unsplashの場合のみクエリパラメータを追加
            thumbnail_url = url
            if 'unsplash.com' in url:
                thumbnail_url = f"{url}?w=400&h=400&fit=crop"

            html_parts.append(f'''
                <div class="gallery-item" onclick="openModal('{url}')">
                    <img src="{thumbnail_url}" alt="{alt}">
                </div>
            ''')
        return '\n'.join(html_parts)

    def _generate_reviews_html(self, reviews: list) -> str:
        """レビューHTMLを生成"""
        if not reviews:
            return '<p style="text-align: center; color: #999;">レビュー情報がありません</p>'

        html_parts = []
        # 匿名性を高めるため、レビュアー名を「利用者A」「利用者B」に変換
        anonymous_labels = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']

        for idx, review in enumerate(reviews[:3]):  # 最大3個
            stars = '★' * review.get('rating', 3) + '☆' * (5 - review.get('rating', 3))

            # 匿名化：reviewer_initialのみ使用、名前は「利用者X」形式に統一
            initial = review.get('reviewer_initial', anonymous_labels[idx % len(anonymous_labels)])
            if len(initial) > 1:
                initial = initial[0].upper()  # 1文字に統一

            anonymous_name = f"利用者{initial}"

            html_parts.append(f'''
                <div class="review-card">
                    <div class="review-header">
                        <div class="reviewer-info">
                            <div class="reviewer-avatar">{initial}</div>
                            <div>
                                <div class="reviewer-name">{anonymous_name}</div>
                                <div class="review-date">{review.get('date', '最近')}</div>
                            </div>
                        </div>
                        <div class="review-rating">{stars}</div>
                    </div>
                    <div class="review-content">{review.get('content', '')}</div>
                </div>
            ''')
        return '\n'.join(html_parts)

    def _generate_detailed_analysis_html(self, detailed_analysis: dict) -> str:
        """詳細分析セクションのHTMLを生成"""
        if not detailed_analysis or not detailed_analysis.get('sections'):
            return ''

        sections = detailed_analysis.get('sections', [])
        sections_html = []

        for section in sections:
            heading = section.get('heading', '分析項目')
            content = section.get('content', '')
            sections_html.append(f'''
                <h3 style="font-size: 20px; font-weight: 700; color: #ff6b6b; margin-bottom: 15px;">{heading}</h3>
                <p style="margin-bottom: 20px;">{content}</p>
            ''')

        return '\n'.join(sections_html)

    def _generate_recommendation_html(self, recommendation: dict) -> str:
        """おすすめポイントHTMLを生成"""
        if not recommendation or not recommendation.get('content'):
            return ''

        content = recommendation.get('content', '')
        # 改行を<br>タグに変換
        content = content.replace('\n', '<br>')

        return content

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

    def _get_html_template(self, **kwargs) -> str:
        """
        完全なHTMLテンプレートを生成
        
        Args:
            **kwargs: テンプレート変数
        
        Returns:
            完全なHTML文字列
        """
        # テンプレートファイルからCSS部分を抽出
        template_path = Path(__file__).parent.parent / 'templates' / 'restaurant_template.html'
        
        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        
        # CSS部分を抽出（<!--から</style>まで）
        css_match = re.search(r'(<!--.*?</style>)', template_content, re.DOTALL)
        if css_match:
            css_content = css_match.group(1)
        else:
            logger.warning("Could not extract CSS from template, using empty CSS")
            css_content = "<style></style>"
        
        # HTMLを構築
        html = build_complete_html(css_content, **kwargs)
        
        return html
