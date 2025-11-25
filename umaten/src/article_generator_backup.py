"""
記事生成モジュール
Claude APIを使用して店舗情報から記事を生成
"""

import anthropic
import json
import logging
from typing import Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class ArticleGenerator:
    """Claude APIを使用した記事生成クラス"""

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
        self.max_tokens = self.claude_config.get('max_tokens', 16000)
        self.temperature = self.claude_config.get('temperature', 0.7)

        # プロンプトテンプレートを読み込み
        template_path = Path(__file__).parent.parent / 'config' / 'prompt_template.txt'
        if template_path.exists():
            with open(template_path, 'r', encoding='utf-8') as f:
                self.prompt_template = f.read()
        else:
            logger.warning("Prompt template not found, using default")
            self.prompt_template = self._get_default_prompt()

    def _get_default_prompt(self) -> str:
        """デフォルトプロンプトを取得"""
        return """
上記の店舗情報から、WordPressに投稿する記事を生成してください。
提供されたHTMLテンプレートの形式に従い、色やスタイルを変えずに記事を作成してください。
"""

    def generate_article(self, restaurant_data: Dict, html_template: str) -> Dict:
        """
        店舗データから記事を生成

        Args:
            restaurant_data: スクレイピングした店舗データ
            html_template: HTMLテンプレート

        Returns:
            生成された記事データ（HTML、SEO情報など）
        """
        logger.info(f"Generating article for: {restaurant_data.get('name', 'Unknown')}")

        # プロンプトを構築
        prompt = self._build_prompt(restaurant_data, html_template)

        try:
            # Claude APIで記事を生成
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

            # レスポンスからテキストを抽出
            article_text = response.content[0].text

            # レスポンスの完全性をチェック
            stop_reason = response.stop_reason
            logger.info(f"Claude API stop_reason: {stop_reason}")
            if stop_reason == "max_tokens":
                logger.warning("Response was truncated due to max_tokens limit!")
                logger.warning(f"Response length: {len(article_text)} characters")

            # 記事データをパース
            article_data = self._parse_article_response(article_text, restaurant_data)

            logger.info("Article generated successfully")
            return article_data

        except Exception as e:
            logger.error(f"Error generating article: {e}")
            raise

    def _build_prompt(self, restaurant_data: Dict, html_template: str) -> str:
        """
        プロンプトを構築

        Args:
            restaurant_data: 店舗データ
            html_template: HTMLテンプレート

        Returns:
            構築されたプロンプト
        """
        # 店舗データをJSON形式で整形
        data_json = json.dumps(restaurant_data, ensure_ascii=False, indent=2)

        # 画像URLリストを整形
        images_text = "\n".join([f"- {img}" for img in restaurant_data.get('images', [])])

        prompt = f"""
以下の店舗データを元に、WordPressのカスタムHTMLブロックに貼り付け可能な完全なHTMLコードを生成してください。

【店舗URL】
{restaurant_data.get('url', '不明')}

【店舗データ（JSON形式）】
```json
{data_json}
```

【利用可能な写真URL】
{images_text if images_text else '写真情報なし'}

【必須】以下の完全なHTMLテンプレートをそのまま使用してください：
{html_template}

{self.prompt_template}
"""

        return prompt

    def _parse_article_response(self, response_text: str, restaurant_data: Dict) -> Dict:
        """
        Claude APIのレスポンスをパース

        Args:
            response_text: APIレスポンステキスト
            restaurant_data: 元の店舗データ

        Returns:
            パースされた記事データ
        """
        article_data = {
            'restaurant_name': restaurant_data.get('name', '不明'),
            'source_url': restaurant_data.get('url', ''),
            'html_content': '',
            'seo_title': '',
            'meta_description': '',
            'slug': '',
            'category': '',
            'tags': [],
        }

        # HTMLコンテンツとSEO情報を分離
        seo_separator = '---SEO情報---'

        if seo_separator in response_text:
            # SEO情報がある場合は分離
            parts = response_text.split(seo_separator)
            html_part = parts[0].strip()
            seo_part = parts[1].strip() if len(parts) > 1 else ''
        else:
            # SEO情報がない場合は全体をHTMLとして扱う
            html_part = response_text
            seo_part = ''

        # HTMLコンテンツを抽出（<!-- から始まり、最後の</script>で終わる）
        import re

        # HTMLコメント開始位置を探す
        html_start = html_part.find('<!--')
        if html_start == -1:
            # コメントが見つからない場合、<style>タグを探す
            html_start = html_part.find('<style>')

        if html_start != -1:
            # 最後の</script>を探す
            last_script_end = html_part.rfind('</script>')
            if last_script_end != -1:
                article_data['html_content'] = html_part[html_start:last_script_end + 9].strip()
                logger.info(f"HTML extracted successfully (length: {len(article_data['html_content'])} characters)")
            else:
                # </script>が見つからない場合、HTMLが不完全
                logger.warning("HTML appears incomplete: </script> tag not found!")
                article_data['html_content'] = html_part[html_start:].strip()
                logger.warning(f"Using incomplete HTML (length: {len(article_data['html_content'])} characters)")
        else:
            # HTMLタグが見つからない場合、全文を使用
            logger.warning("HTML start tag not found!")
            article_data['html_content'] = html_part.strip()

        # SEO情報を抽出
        if seo_part:
            for line in seo_part.split('\n'):
                line = line.strip()
                if line.startswith('SEOタイトル:'):
                    article_data['seo_title'] = line.replace('SEOタイトル:', '').strip()
                elif line.startswith('メタディスクリプション:'):
                    article_data['meta_description'] = line.replace('メタディスクリプション:', '').strip()
                elif line.startswith('スラッグ:'):
                    article_data['slug'] = line.replace('スラッグ:', '').strip()
                elif line.startswith('カテゴリ:'):
                    category_text = line.replace('カテゴリ:', '').strip()
                    # カテゴリスラッグを抽出
                    if '(' in category_text and ')' in category_text:
                        article_data['category'] = category_text.split('(')[1].split(')')[0]
                    else:
                        article_data['category'] = category_text

        # デフォルト値を設定
        if not article_data['seo_title']:
            article_data['seo_title'] = f"{restaurant_data.get('name', '店舗')} | ウマ店"

        if not article_data['meta_description']:
            category = restaurant_data.get('category', ['飲食店'])[0] if restaurant_data.get('category') else '飲食店'
            article_data['meta_description'] = f"{restaurant_data.get('name', '店舗')}の詳細情報。{category}。営業時間、メニュー、口コミなど。"

        if not article_data['slug']:
            # 店舗名からスラッグを生成
            import re
            name = restaurant_data.get('name', 'restaurant')
            slug = re.sub(r'[^\w\s-]', '', name.lower())
            slug = re.sub(r'[\s_]+', '-', slug)
            article_data['slug'] = slug[:50]  # 最大50文字

        if not article_data['category']:
            # カテゴリマッピングから推測
            categories = restaurant_data.get('category', [])
            if categories:
                category_mapping = self.config.get('category_mapping', {})
                for cat in categories:
                    if cat in category_mapping:
                        article_data['category'] = category_mapping[cat]
                        break

                # まだ見つからない場合、デフォルト
                if not article_data['category']:
                    article_data['category'] = 'western-food'  # デフォルトカテゴリ
            else:
                article_data['category'] = 'western-food'

        logger.info(f"Parsed article data: title={article_data['seo_title']}, category={article_data['category']}")
        return article_data

    def load_html_template(self, template_path: Optional[str] = None) -> str:
        """
        HTMLテンプレートを読み込み

        Args:
            template_path: テンプレートファイルのパス（Noneの場合はデフォルト）

        Returns:
            HTMLテンプレート文字列
        """
        if template_path:
            path = Path(template_path)
        else:
            path = Path(__file__).parent.parent / 'templates' / 'restaurant_template.html'

        if path.exists():
            logger.info(f"Loading HTML template from: {path}")
            with open(path, 'r', encoding='utf-8') as f:
                template_content = f.read()
                logger.info(f"Template loaded successfully ({len(template_content)} characters)")
                return template_content
        else:
            logger.error(f"Template not found at {path}")
            raise FileNotFoundError(f"HTMLテンプレートが見つかりません: {path}")
