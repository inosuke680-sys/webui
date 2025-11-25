"""
Webスクレイピングモジュール
食べログなどのサイトから店舗情報を取得
"""

import time
import random
import re
import requests
from bs4 import BeautifulSoup
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse
from fake_useragent import UserAgent
from retry import retry
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class RestaurantScraper:
    """レストラン情報スクレイパー"""

    def __init__(self, config: Dict):
        """
        初期化

        Args:
            config: 設定辞書
        """
        self.config = config
        self.scraping_config = config.get('scraping', {})
        self.session = requests.Session()
        self.ua = UserAgent()

    def _get_headers(self, referer: Optional[str] = None) -> Dict[str, str]:
        """
        ランダムなUser-Agentを含むヘッダーを取得

        Args:
            referer: Refererヘッダー（オプション）

        Returns:
            ヘッダー辞書
        """
        user_agents = self.scraping_config.get('user_agents', [])
        if user_agents:
            user_agent = random.choice(user_agents)
        else:
            user_agent = self.ua.random

        headers = {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin' if referer else 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        }

        # Refererがある場合は追加（サイト内遷移を模倣）
        if referer:
            headers['Referer'] = referer

        return headers

    def _random_delay(self):
        """ランダムな遅延を挿入（アクセス制限対策）"""
        min_delay = self.scraping_config.get('min_delay', 2)
        max_delay = self.scraping_config.get('max_delay', 5)
        delay = random.uniform(min_delay, max_delay)
        logger.debug(f"Waiting {delay:.2f} seconds...")
        time.sleep(delay)

    @staticmethod
    def normalize_restaurant_url(url: str) -> str:
        """
        食べログの店舗URLを正規化

        店舗詳細ページのURLに統一し、重複を防ぐ
        例: /hokkaido/A0112/A011203/1011581/dtlrvwlst/ → /hokkaido/A0112/A011203/1011581/

        Args:
            url: 正規化するURL

        Returns:
            正規化されたURL
        """
        # クエリパラメータとフラグメントを除去
        url = url.split('?')[0].split('#')[0]

        # 店舗URLのパターン: /地域/Aコード/Aコード/店舗ID/ の後に続く余分なパスを削除
        # サブページ（dtlrvwlst, dtlphotolst など）を削除して店舗詳細ページに統一
        match = re.match(r'(https?://[^/]+/[^/]+/A\d+/A\d+/\d+)/?.*', url)
        if match:
            return match.group(1) + '/'
        else:
            # パターンにマッチしない場合は末尾のスラッシュを統一
            return url.rstrip('/') + '/'

    @retry(tries=3, delay=2, backoff=2, logger=logger)
    def _fetch_page(self, url: str, referer: Optional[str] = None) -> Optional[str]:
        """
        ページを取得

        Args:
            url: URL
            referer: Refererヘッダー（オプション）

        Returns:
            HTMLコンテンツ
        """
        try:
            headers = self._get_headers(referer=referer)
            timeout = self.scraping_config.get('timeout', 30)

            logger.info(f"Fetching: {url}")
            response = self.session.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            response.encoding = response.apparent_encoding

            self._random_delay()
            return response.text

        except requests.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            raise

    def get_max_page_number(self, list_url: str) -> int:
        """
        食べログのリストページから最終ページ番号を取得

        Args:
            list_url: リストページのURL

        Returns:
            最終ページ番号（取得できない場合は1）
        """
        try:
            html = self._fetch_page(list_url)
            if not html:
                return 1

            soup = BeautifulSoup(html, 'lxml')

            # ページネーションから最終ページを探す
            # 食べログのページネーションは <a> タグや <span> タグで構成される
            max_page = 1

            # パターン1: c-pagination クラス内のリンクをチェック
            pagination = soup.find('nav', class_='c-pagination')
            if pagination:
                page_links = pagination.find_all('a', class_='c-pagination__target')
                for link in page_links:
                    try:
                        page_num = int(link.get_text(strip=True))
                        max_page = max(max_page, page_num)
                    except (ValueError, AttributeError):
                        continue

            # パターン2: rstlst-pager クラス内のリンクをチェック
            pager = soup.find('div', class_='rstlst-pager')
            if pager:
                page_links = pager.find_all('a')
                for link in page_links:
                    try:
                        page_num = int(link.get_text(strip=True))
                        max_page = max(max_page, page_num)
                    except (ValueError, AttributeError):
                        continue

            # パターン3: URLパターンから推測（/rstLst/数字/ の形式）
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href')
                if href and '/rstLst/' in href:
                    # /rstLst/3/ のような形式を抽出
                    parts = href.split('/rstLst/')
                    if len(parts) > 1:
                        page_part = parts[1].split('/')[0]
                        try:
                            page_num = int(page_part)
                            max_page = max(max_page, page_num)
                        except (ValueError, IndexError):
                            continue

            logger.info(f"Detected max page number: {max_page} for {list_url}")
            return max_page

        except Exception as e:
            logger.error(f"Failed to get max page number: {e}")
            return 1

    def scrape_restaurant_list(self, list_url: str, include_all_pages: bool = False) -> List[str]:
        """
        食べログのリストページから店舗URLを抽出

        Args:
            list_url: リストページのURL
            include_all_pages: True の場合、最終ページまでの全ページから抽出

        Returns:
            店舗URLのリスト
        """
        logger.info(f"Scraping restaurant list: {list_url} (include_all_pages={include_all_pages})")

        all_restaurant_urls = []

        # 全ページ処理が有効な場合、最終ページ番号を取得
        if include_all_pages:
            max_page = self.get_max_page_number(list_url)
            logger.info(f"Will scrape pages 1 to {max_page}")

            # 1ページ目から最終ページまで処理
            for page_num in range(1, max_page + 1):
                # ページURLを生成
                if page_num == 1:
                    page_url = list_url
                else:
                    # /rstLst/ の後にページ番号を追加
                    # 例: https://tabelog.com/hokkaido/A0105/A010501/rstLst/ → .../rstLst/2/
                    base_url = list_url.rstrip('/')
                    if '/rstLst' in base_url:
                        page_url = f"{base_url}/{page_num}/"
                    elif '/lst' in base_url:
                        page_url = f"{base_url}/{page_num}/"
                    else:
                        page_url = f"{base_url}/{page_num}/"

                logger.info(f"Scraping page {page_num}/{max_page}: {page_url}")

                # ページから店舗URLを抽出
                page_urls = self._extract_restaurant_urls_from_page(page_url)
                all_restaurant_urls.extend(page_urls)

                # レート制限対策：各ページの間に待機
                if page_num < max_page:
                    time.sleep(random.uniform(1, 2))
        else:
            # 1ページ目のみ処理
            all_restaurant_urls = self._extract_restaurant_urls_from_page(list_url)

        # 重複を除去
        unique_urls = list(dict.fromkeys(all_restaurant_urls))
        logger.info(f"Found {len(unique_urls)} unique restaurant URLs")
        return unique_urls

    def _extract_restaurant_urls_from_page(self, page_url: str) -> List[str]:
        """
        単一ページから店舗URLを抽出（内部メソッド）

        Args:
            page_url: ページのURL

        Returns:
            店舗URLのリスト
        """
        html = self._fetch_page(page_url)
        if not html:
            return []

        soup = BeautifulSoup(html, 'lxml')
        restaurant_urls = []

        # リストページから店舗リンクを抽出
        # 食べログの店舗詳細ページは /A\d+/A\d+/A\d+/\d+/ の形式
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            # 店舗詳細ページのパターンにマッチ
            if href and '/A' in href and href.count('/') >= 5:
                # 相対URLを絶対URLに変換
                full_url = urljoin(page_url, href)
                # tabelog.comのドメインチェック
                if 'tabelog.com' in full_url:
                    # URL正規化（サブページを削除し、店舗詳細ページに統一）
                    clean_url = self.normalize_restaurant_url(full_url)

                    # 重複チェック（リストページ自体は除外）
                    if '/rstLst/' not in clean_url and '/lst/' not in clean_url:
                        restaurant_urls.append(clean_url)

        return restaurant_urls

    def scrape_tabelog(self, url: str) -> Dict:
        """
        食べログから店舗情報をスクレイピング

        Args:
            url: 食べログのURL

        Returns:
            店舗情報辞書
        """
        logger.info(f"Scraping Tabelog: {url}")

        # メインページを取得
        html = self._fetch_page(url)
        if not html:
            return {}

        soup = BeautifulSoup(html, 'lxml')

        # 基本情報を抽出
        data = {
            'url': url,
            'name': self._extract_name(soup),
            'category': self._extract_category(soup),
            'rating': self._extract_rating(soup),
            'review_count': self._extract_review_count(soup),
            'address': self._extract_address(soup),
            'station': self._extract_station(soup),
            'phone': self._extract_phone(soup),
            'business_hours': self._extract_business_hours(soup),
            'holiday': self._extract_holiday(soup),
            'budget': self._extract_budget(soup),
            'seats': self._extract_seats(soup),
            'smoking': self._extract_smoking(soup),
            'parking': self._extract_parking(soup),
            'payment': self._extract_payment(soup),
            'description': self._extract_description(soup),
            'official_website': self._extract_official_website(soup),
            'photo_count': self._extract_photo_count(soup),  # ナビゲーションから写真枚数を取得
            'images': [],
            'reviews': [],
        }

        # 写真ページのURLを取得
        photo_url = self._get_photo_page_url(soup, url)
        if photo_url:
            data['images'] = self.scrape_tabelog_photos(photo_url, referer=url)

        # レビューを取得
        data['reviews'] = self._extract_reviews(soup)

        logger.info(f"Scraped data: {data['name']}")
        return data

    def _get_photo_page_url(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        """
        写真ページのURLを取得

        Args:
            soup: BeautifulSoupオブジェクト
            base_url: ベースURL

        Returns:
            写真ページのURL
        """
        # <a class="mainnavi" href="...dtlphotolst...">を探す
        photo_link = soup.find('a', class_='mainnavi', href=lambda x: x and 'dtlphotolst' in x)
        if photo_link:
            return urljoin(base_url, photo_link.get('href'))

        # または dtlphotolst を含むリンクを探す
        for link in soup.find_all('a', href=True):
            href = link.get('href')
            if 'dtlphotolst' in href or 'photo' in href.lower():
                return urljoin(base_url, href)

        return None

    def scrape_tabelog_photos(self, photo_url: str, referer: Optional[str] = None) -> List[str]:
        """
        食べログの写真ページから画像URLを取得

        Args:
            photo_url: 写真ページのURL
            referer: Refererヘッダー（オプション）

        Returns:
            画像URLのリスト
        """
        logger.info(f"Scraping photos from: {photo_url}")

        html = self._fetch_page(photo_url, referer=referer)
        if not html:
            logger.warning("Failed to fetch photo page HTML")
            return []

        # デバッグ用：HTMLを保存
        debug_dir = Path(__file__).parent.parent / 'logs'
        debug_dir.mkdir(exist_ok=True)
        debug_file = debug_dir / 'photo_page_debug.html'
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(html)
        logger.info(f"DEBUG: Saved photo page HTML to: {debug_file}")

        soup = BeautifulSoup(html, 'lxml')
        images = []

        # 方法1: aタグのhref属性から画像URLを取得（最も確実）
        logger.info("Method 1: Extracting image URLs from <a> tag href attributes")
        a_tags = soup.find_all('a', href=True)
        logger.info(f"Found {len(a_tags)} <a> tags on page")

        img_count = 0
        for a_tag in a_tags:
            href = a_tag.get('href')
            # tblg.k-img.comドメインの画像URLを全て取得
            if href and 'tblg.k-img.com' in href and any(ext in href for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                # 任意のサイズを640x640に変換
                full_url = self._convert_to_full_image(href)
                if full_url not in images:
                    images.append(full_url)
                    img_count += 1
                    if img_count <= 5:  # 最初の5つだけ詳細ログ
                        logger.info(f"  ✓ Image {img_count}: {full_url[:80]}...")

        logger.info(f"Method 1 result: Found {img_count} images from <a> tags")

        # 方法2: imgタグのsrc属性から取得（補助的）
        if len(images) == 0:
            logger.info("Method 2: Extracting from <img> tags as fallback")
            img_tags = soup.find_all('img', src=True)
            logger.info(f"Found {len(img_tags)} <img> tags with src")

            for img in img_tags:
                src = img.get('src') or img.get('data-src') or img.get('data-original')
                if src and 'tblg.k-img.com' in src:
                    full_url = self._convert_to_full_image(src)
                    if full_url not in images:
                        images.append(full_url)
                        logger.info(f"  ✓ Added from <img> tag: {full_url[:80]}...")

            logger.info(f"Method 2 result: Total images now: {len(images)}")

        # 方法3: JSON-LD構造化データから取得
        if len(images) == 0:
            logger.info("Method 3: Trying to extract from JSON-LD structured data")
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            logger.info(f"Found {len(json_ld_scripts)} JSON-LD scripts")

            import json as json_lib
            for script in json_ld_scripts:
                try:
                    data = json_lib.loads(script.string)
                    if isinstance(data, dict) and 'image' in data:
                        image_data = data['image']
                        if isinstance(image_data, str):
                            images.append(self._convert_to_full_image(image_data))
                            logger.info(f"  ✓ Found image in JSON-LD: {image_data[:80]}...")
                        elif isinstance(image_data, list):
                            for img_url in image_data:
                                if isinstance(img_url, str):
                                    images.append(self._convert_to_full_image(img_url))
                                    logger.info(f"  ✓ Found image in JSON-LD: {img_url[:80]}...")
                except:
                    pass

            logger.info(f"Method 3 result: Total images now: {len(images)}")

        logger.info(f"Found {len(images)} images")
        return images

    def _convert_to_full_image(self, url: str) -> str:
        """
        サムネイルURLを高解像度画像URLに変換

        Args:
            url: サムネイルURL

        Returns:
            高解像度画像URL
        """
        # 食べログの画像URLパターンを変換
        if 'tblg.k-img.com' in url:
            # 各種サムネイルサイズを640x640に変換
            url = url.replace('150x150_square', '640x640_rect')
            url = url.replace('320x320_rect', '640x640_rect')
            url = url.replace('240x240_square', '640x640_rect')
            url = url.replace('120x120_square', '640x640_rect')
            url = url.replace('/s/', '/m/')

        return url

    def _extract_name(self, soup: BeautifulSoup) -> str:
        """店舗名を抽出"""
        # h1タグから取得
        h1 = soup.find('h1')
        if h1:
            return h1.get_text(strip=True)

        # data-detail-page属性から取得
        detail_div = soup.find('div', {'data-detail-page': True})
        if detail_div:
            return detail_div.get('data-detail-page', '')

        return "不明"

    def _extract_category(self, soup: BeautifulSoup) -> List[str]:
        """カテゴリを抽出"""
        categories = []

        # カテゴリリンクから取得
        for link in soup.find_all('a', href=lambda x: x and '/lst/cat' in x):
            category = link.get_text(strip=True)
            if category and category not in categories:
                categories.append(category)

        return categories

    def _extract_rating(self, soup: BeautifulSoup) -> Optional[float]:
        """評価スコアを抽出"""
        # 評価スコアを含む要素を探す
        rating_elem = soup.find('span', class_=lambda x: x and 'rdheader-rating__score' in x)
        if rating_elem:
            try:
                return float(rating_elem.get_text(strip=True))
            except ValueError:
                pass

        # その他のパターン
        for elem in soup.find_all('span', class_=lambda x: x and 'rating' in x.lower()):
            text = elem.get_text(strip=True)
            try:
                return float(text)
            except ValueError:
                continue

        return None

    def _extract_review_count(self, soup: BeautifulSoup) -> int:
        """レビュー数を抽出"""
        # レビュー数を含む要素を探す
        for elem in soup.find_all(['span', 'em'], class_=lambda x: x and 'count' in x.lower()):
            text = elem.get_text(strip=True)
            # 数字のみ抽出
            import re
            numbers = re.findall(r'\d+', text)
            if numbers:
                return int(numbers[0])

        return 0

    def _extract_address(self, soup: BeautifulSoup) -> str:
        """住所を抽出"""
        # 住所を含む要素を探す
        address_elem = soup.find('p', class_=lambda x: x and 'address' in x.lower())
        if address_elem:
            return address_elem.get_text(strip=True)

        # テーブルから抽出
        for th in soup.find_all('th'):
            if '住所' in th.get_text():
                td = th.find_next_sibling('td')
                if td:
                    return td.get_text(strip=True)

        return "不明"

    def _extract_station(self, soup: BeautifulSoup) -> str:
        """最寄り駅を抽出"""
        for th in soup.find_all('th'):
            if '交通手段' in th.get_text() or '最寄り駅' in th.get_text():
                td = th.find_next_sibling('td')
                if td:
                    return td.get_text(strip=True)

        return "不明"

    def _extract_phone(self, soup: BeautifulSoup) -> str:
        """電話番号を抽出"""
        for th in soup.find_all('th'):
            if '電話番号' in th.get_text():
                td = th.find_next_sibling('td')
                if td:
                    return td.get_text(strip=True)

        return "不明"

    def _extract_official_website(self, soup: BeautifulSoup) -> Optional[str]:
        """公式サイト・ホームページのURLを抽出"""
        # テーブルから「ホームページ」「公式サイト」「URL」などを探す
        for th in soup.find_all('th'):
            th_text = th.get_text(strip=True)
            if any(keyword in th_text for keyword in ['ホームページ', '公式', 'URL', 'Webサイト', 'ウェブサイト']):
                td = th.find_next_sibling('td')
                if td:
                    # tdの中のリンクを探す
                    link = td.find('a', href=True)
                    if link:
                        href = link.get('href')
                        # 外部リンク（tabelog以外）のみを取得
                        if href and 'tabelog.com' not in href:
                            return href

        # 別の方法：外部リンクアイコンやclass名で探す
        for link in soup.find_all('a', href=True):
            link_text = link.get_text(strip=True)
            if any(keyword in link_text for keyword in ['ホームページ', '公式サイト', '公式ページ', 'オフィシャルサイト']):
                href = link.get('href')
                if href and 'tabelog.com' not in href:
                    return href

        # SNSやその他の外部リンクがある場合でも、明確に「公式」と書かれているものを優先
        # ただし、食べログのページ自体を返さないようにする
        return None

    def _extract_photo_count(self, soup: BeautifulSoup) -> int:
        """
        ナビゲーションから写真枚数を抽出

        Args:
            soup: BeautifulSoupオブジェクト

        Returns:
            写真枚数（取得できない場合は0）
        """
        try:
            # ナビゲーション内の写真枚数を探す
            # <li id="rdnavi-photo">内の<span class="rstdtl-navi__total-count"><strong>298</strong></span>
            photo_nav = soup.find('li', id='rdnavi-photo')
            if photo_nav:
                total_count = photo_nav.find('span', class_='rstdtl-navi__total-count')
                if total_count:
                    strong = total_count.find('strong')
                    if strong:
                        count_text = strong.get_text(strip=True)
                        photo_count = int(count_text)
                        logger.info(f"写真枚数をナビゲーションから取得: {photo_count}枚")
                        return photo_count

            # 別の方法：class_='rstdtl-navi__total-count'を直接探す
            total_count = soup.find('span', class_='rstdtl-navi__total-count')
            if total_count:
                strong = total_count.find('strong')
                if strong:
                    count_text = strong.get_text(strip=True)
                    photo_count = int(count_text)
                    logger.info(f"写真枚数を取得: {photo_count}枚")
                    return photo_count

            logger.warning("写真枚数を取得できませんでした")
            return 0

        except Exception as e:
            logger.warning(f"写真枚数の抽出中にエラーが発生: {e}")
            return 0

    def _extract_business_hours(self, soup: BeautifulSoup) -> str:
        """営業時間を抽出"""
        for th in soup.find_all('th'):
            if '営業時間' in th.get_text():
                td = th.find_next_sibling('td')
                if td:
                    return td.get_text(strip=True)

        return "不明"

    def _extract_holiday(self, soup: BeautifulSoup) -> str:
        """定休日を抽出"""
        for th in soup.find_all('th'):
            if '定休日' in th.get_text():
                td = th.find_next_sibling('td')
                if td:
                    return td.get_text(strip=True)

        return "不明"

    def _extract_budget(self, soup: BeautifulSoup) -> Dict[str, str]:
        """予算を抽出"""
        budget = {'lunch': '不明', 'dinner': '不明'}

        for th in soup.find_all('th'):
            text = th.get_text(strip=True)
            td = th.find_next_sibling('td')
            if not td:
                continue

            if 'ランチ' in text or 'Lunch' in text:
                budget['lunch'] = td.get_text(strip=True)
            elif 'ディナー' in text or 'Dinner' in text:
                budget['dinner'] = td.get_text(strip=True)
            elif '予算' in text and budget['dinner'] == '不明':
                budget['dinner'] = td.get_text(strip=True)

        return budget

    def _extract_seats(self, soup: BeautifulSoup) -> str:
        """座席数を抽出"""
        for th in soup.find_all('th'):
            if '座席' in th.get_text():
                td = th.find_next_sibling('td')
                if td:
                    return td.get_text(strip=True)

        return "不明"

    def _extract_smoking(self, soup: BeautifulSoup) -> str:
        """喫煙情報を抽出"""
        for th in soup.find_all('th'):
            if '喫煙' in th.get_text() or '禁煙' in th.get_text():
                td = th.find_next_sibling('td')
                if td:
                    return td.get_text(strip=True)

        return "不明"

    def _extract_parking(self, soup: BeautifulSoup) -> str:
        """駐車場情報を抽出"""
        for th in soup.find_all('th'):
            if '駐車場' in th.get_text():
                td = th.find_next_sibling('td')
                if td:
                    return td.get_text(strip=True)

        return "不明"

    def _extract_payment(self, soup: BeautifulSoup) -> str:
        """支払い方法を抽出"""
        for th in soup.find_all('th'):
            if '支払' in th.get_text() or 'カード' in th.get_text():
                td = th.find_next_sibling('td')
                if td:
                    return td.get_text(strip=True)

        return "不明"

    def _extract_description(self, soup: BeautifulSoup) -> str:
        """説明文を抽出"""
        # 説明文を含む要素を探す
        desc_elem = soup.find('div', class_=lambda x: x and 'description' in x.lower())
        if desc_elem:
            return desc_elem.get_text(strip=True)

        return ""

    def _extract_reviews(self, soup: BeautifulSoup) -> List[Dict]:
        """レビューを抽出"""
        reviews = []

        # レビューコンテナを探す
        review_containers = soup.find_all('div', class_=lambda x: x and 'review' in x.lower())

        for container in review_containers[:10]:  # 最大10件
            review = {}

            # レビュアー名
            reviewer = container.find('a', class_=lambda x: x and 'reviewer' in x.lower())
            if reviewer:
                review['reviewer'] = reviewer.get_text(strip=True)

            # 日付
            date_elem = container.find('span', class_=lambda x: x and 'date' in x.lower())
            if date_elem:
                review['date'] = date_elem.get_text(strip=True)

            # 評価
            rating_elem = container.find('span', class_=lambda x: x and 'rating' in x.lower())
            if rating_elem:
                review['rating'] = rating_elem.get_text(strip=True)

            # レビュー本文
            text_elem = container.find('div', class_=lambda x: x and 'comment' in x.lower())
            if text_elem:
                review['text'] = text_elem.get_text(strip=True)

            if review:
                reviews.append(review)

        return reviews
