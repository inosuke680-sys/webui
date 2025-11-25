"""
HTML構築ヘルパー
"""
from urllib.parse import quote

def build_complete_html(css_content: str, **kwargs) -> str:
    """
    完全なHTMLを構築

    Args:
        css_content: CSS content
        **kwargs: テンプレート変数

    Returns:
        完全なHTML文字列
    """
    name = kwargs.get('name', '不明')
    category = kwargs.get('category', 'その他')
    area = kwargs.get('area', '不明')
    rating_value = kwargs.get('rating_value', 3.5)
    stars_display = kwargs.get('stars_display', '★★★☆☆')
    rating_food = kwargs.get('rating_food', 3.5)
    rating_service = kwargs.get('rating_service', 3.5)
    rating_atmosphere = kwargs.get('rating_atmosphere', 3.4)
    rating_value_money = kwargs.get('rating_value_money', 3.7)
    address = kwargs.get('address', '不明')
    address_encoded = quote(address) if address and address != '不明' else ''
    access = kwargs.get('access', '不明')
    business_hours = kwargs.get('business_hours', '不明')
    regular_holiday = kwargs.get('regular_holiday', '不明')
    budget_lunch = kwargs.get('budget_lunch', '不明')
    budget_dinner = kwargs.get('budget_dinner', '不明')
    smoking = kwargs.get('smoking', '不明')
    parking = kwargs.get('parking', '不明')
    phone = kwargs.get('phone', '')
    source_url = kwargs.get('source_url', '#')
    official_website = kwargs.get('official_website', '')
    hero_image = kwargs.get('hero_image', 'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=1200&h=400&fit=crop')
    menu_html = kwargs.get('menu_html', '')
    gallery_html = kwargs.get('gallery_html', '')
    reviews_html = kwargs.get('reviews_html', '')
    detailed_analysis_html = kwargs.get('detailed_analysis_html', '')
    recommendation_html = kwargs.get('recommendation_html', '')
    seo_text = kwargs.get('seo_text', '')

    # 公式サイトがある場合は優先的に使用、ない場合は食べログURL
    detail_url = official_website if official_website else source_url
    detail_button_text = '🌐 公式サイトを見る' if official_website else '🌐 詳細を見る（食べログ）'

    phone_display = phone if phone and phone != '不明' else '電話番号未公開'
    phone_button = f'<a href="tel:{phone}" class="action-button primary">📞 電話する</a>' if phone and phone != '不明' else '<span class="action-button primary" style="opacity: 0.6; cursor: not-allowed;">📞 電話番号未公開</span>'
    
    # パーセンテージ計算
    food_pct = int((rating_food / 5.0) * 100)
    service_pct = int((rating_service / 5.0) * 100)
    atmosphere_pct = int((rating_atmosphere / 5.0) * 100)
    value_pct = int((rating_value_money / 5.0) * 100)
    
    html = f"""<!--
=====================================
ウマ店 店舗詳細ページテンプレート
WordPress Swellテーマ用カスタムHTML
=====================================
-->

{css_content}

<div class="restaurant-detail-wrapper">
    <!-- ヒーローセクション -->
    <section class="restaurant-hero">
        <img src="{hero_image}" alt="{name}" class="restaurant-hero-image">
        <div class="restaurant-hero-overlay">
            <h1 class="restaurant-name">{name}</h1>
            <span class="restaurant-category">{category}</span>
            <span class="restaurant-area">{area}</span>
        </div>
    </section>

    <!-- クイックアクション -->
    <div class="restaurant-container">
        <div class="quick-actions">
            {phone_button}
            <a href="{detail_url}" class="action-button" target="_blank">{detail_button_text}</a>
            <a href="#map" class="action-button">📍 地図を見る</a>
            <button class="action-button" onclick="shareRestaurant()">📤 シェア</button>
        </div>

        <!-- 評価セクション -->
        <section class="rating-section">
            <div class="rating-header">
                <div class="rating-score">{rating_value:.1f}</div>
                <div>
                    <div class="rating-stars">{stars_display}</div>
                    <div class="rating-count">ウマ店独自評価</div>
                </div>
            </div>
            <div class="rating-breakdown">
                <div class="rating-item">
                    <span class="rating-label">料理</span>
                    <div class="rating-bar">
                        <div class="rating-fill" style="width: {food_pct}%"></div>
                    </div>
                    <span>{rating_food:.1f}</span>
                </div>
                <div class="rating-item">
                    <span class="rating-label">サービス</span>
                    <div class="rating-bar">
                        <div class="rating-fill" style="width: {service_pct}%"></div>
                    </div>
                    <span>{rating_service:.1f}</span>
                </div>
                <div class="rating-item">
                    <span class="rating-label">雰囲気</span>
                    <div class="rating-bar">
                        <div class="rating-fill" style="width: {atmosphere_pct}%"></div>
                    </div>
                    <span>{rating_atmosphere:.1f}</span>
                </div>
                <div class="rating-item">
                    <span class="rating-label">コスパ</span>
                    <div class="rating-bar">
                        <div class="rating-fill" style="width: {value_pct}%"></div>
                    </div>
                    <span>{rating_value_money:.1f}</span>
                </div>
            </div>
        </section>

        <!-- 基本情報グリッド -->
        <h2>📋 基本情報</h2>
        <div class="info-grid">
            <div class="info-card">
                <div class="info-card-icon">📍</div>
                <h3>アクセス</h3>
                <div class="info-row">
                    <span class="info-label">住所</span>
                    <span class="info-value">{address}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">最寄り駅</span>
                    <span class="info-value">{access}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">駐車場</span>
                    <span class="info-value">{parking}</span>
                </div>
            </div>

            <div class="info-card">
                <div class="info-card-icon">🕐</div>
                <h3>営業情報</h3>
                <div class="info-row">
                    <span class="info-label">営業時間</span>
                    <span class="info-value">{business_hours}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">定休日</span>
                    <span class="info-value">{regular_holiday}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">電話番号</span>
                    <span class="info-value">{phone_display}</span>
                </div>
            </div>

            <div class="info-card">
                <div class="info-card-icon">💴</div>
                <h3>価格帯</h3>
                <div class="info-row">
                    <span class="info-label">ランチ</span>
                    <span class="info-value">{budget_lunch}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">ディナー</span>
                    <span class="info-value">{budget_dinner}</span>
                </div>
            </div>

            <div class="info-card">
                <div class="info-card-icon">🏠</div>
                <h3>設備・サービス</h3>
                <div class="info-row">
                    <span class="info-label">喫煙</span>
                    <span class="info-value">{smoking}</span>
                </div>
                <div class="info-row">
                    <span class="info-label">駐車場</span>
                    <span class="info-value">{parking}</span>
                </div>
            </div>
        </div>

        <!-- メニューセクション -->
        <section class="menu-section">
            <h2>🍽️ メニュー</h2>
            <div class="menu-grid">
                {menu_html}
            </div>
        </section>

        <!-- フォトギャラリー -->
        <section class="photo-gallery">
            <h2>📸 フォトギャラリー</h2>
            <div class="gallery-grid">
                {gallery_html}
            </div>
        </section>

        <!-- レビューセクション -->
        <section class="review-section">
            <h2>💬 お客様の声</h2>
            {reviews_html}
        </section>

        <!-- レビュー詳細分析セクション -->
        {f'''
        <div class="review-analysis-section" style="background: #f8f9fa; border-radius: 20px; padding: 30px; margin-bottom: 30px;">
            <h2 style="font-size: 28px !important; font-weight: 900 !important; color: #2c3e50 !important; margin: 0 0 30px 0 !important; padding-left: 15px !important; border-left: 4px solid transparent !important; border-image: linear-gradient(135deg, #ff6b6b, #ff8e53) 1 !important;">📊 レビューの詳細分析と独自評価</h2>
            <div style="background: white; border-radius: 15px; padding: 25px; line-height: 1.8; color: #2c3e50;">
                {detailed_analysis_html}
            </div>
        </div>
        ''' if detailed_analysis_html else ''}

        <!-- ウマ店編集部のおすすめセクション -->
        {f'''
        <div class="info-card" style="margin-bottom: 30px;">
            <div class="info-card-icon">💡</div>
            <h3>ウマ店編集部のおすすめ</h3>
            <p style="line-height: 1.8; color: #2c3e50;">
                {recommendation_html}
            </p>
        </div>
        ''' if recommendation_html else ''}

        <!-- アクセス・地図 -->
        <section class="map-section" id="map">
            <h2>📍 アクセス・地図</h2>
            <div class="map-container">
                <iframe
                    width="100%"
                    height="450"
                    style="border:0; border-radius: 12px;"
                    loading="lazy"
                    allowfullscreen
                    referrerpolicy="no-referrer-when-downgrade"
                    src="https://www.google.com/maps/embed/v1/place?key=AIzaSyBFw0Qbyq9zTFTd-tUY6dZWTgaQzuU17R8&q={address_encoded}&zoom=15&language=ja">
                </iframe>
            </div>
            <div class="access-info">
                <div class="access-item">
                    <div class="access-icon">🚃</div>
                    <div>
                        <div style="font-weight: 700; margin-bottom: 5px;">アクセス</div>
                        <div style="color: #666;">{access}</div>
                    </div>
                </div>
                <div class="access-item">
                    <div class="access-icon">📍</div>
                    <div>
                        <div style="font-weight: 700; margin-bottom: 5px;">住所</div>
                        <div style="color: #666;">{address}</div>
                    </div>
                </div>
            </div>
        </section>

        <!-- 関連情報（SEO用） -->
        {f'''
        <div style="margin-top: 50px; padding-top: 30px; border-top: 2px solid #f0f0f0;">
            <p style="font-size: 14px; color: #666; line-height: 1.8;">
                {seo_text}
            </p>
        </div>
        ''' if seo_text else ''}

    </div>
</div>

<div id="imageModal" class="modal" onclick="closeModal()">
    <span class="modal-close">&times;</span>
    <img class="modal-content" id="modalImage">
</div>

<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Restaurant",
  "name": "{name}",
  "image": "{hero_image}",
  "address": {{
    "@type": "PostalAddress",
    "addressLocality": "{area}",
    "streetAddress": "{address}",
    "addressCountry": "JP"
  }},
  "geo": {{
    "@type": "GeoCoordinates",
    "addressCountry": "JP"
  }},
  "url": "{detail_url}",
  "telephone": "{phone}",
  "servesCuisine": "{category}",
  "priceRange": "{budget_dinner}",
  "openingHours": "{business_hours}",
  "aggregateRating": {{
    "@type": "AggregateRating",
    "ratingValue": "{rating_value:.1f}",
    "bestRating": "5",
    "worstRating": "1"
  }},
  "review": {{
    "@type": "Review",
    "author": {{
      "@type": "Organization",
      "name": "ウマ店"
    }},
    "reviewRating": {{
      "@type": "Rating",
      "ratingValue": "{rating_value:.1f}",
      "bestRating": "5"
    }}
  }}
}}
</script>

<script>
function switchMenuTab(tabName, element) {{
    const tabs = document.querySelectorAll('.menu-tab');
    const contents = document.querySelectorAll('.menu-content');
    
    tabs.forEach(tab => tab.classList.remove('active'));
    contents.forEach(content => content.classList.remove('active'));
    
    element.classList.add('active');
    document.getElementById('menu-' + tabName).classList.add('active');
}}

function openModal(imageSrc) {{
    const modal = document.getElementById('imageModal');
    const modalImg = document.getElementById('modalImage');
    modal.style.display = 'block';
    modalImg.src = imageSrc;
}}

function closeModal() {{
    const modal = document.getElementById('imageModal');
    modal.style.display = 'none';
}}

function shareRestaurant() {{
    if (navigator.share) {{
        navigator.share({{
            title: '{name}',
            text: 'おすすめのお店を見つけました！',
            url: window.location.href
        }});
    }} else {{
        alert('このブラウザでは共有機能がサポートされていません');
    }}
}}
</script>
"""
    
    return html
