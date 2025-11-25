// WebSocket接続
const socket = io();

// グローバル変数
let categories = [];
let selectedCategoryIds = [];
let jobs = {};
let urlCategoryData = {}; // URL行ごとのカテゴリID {urlIndex: [categoryIds]}
let currentEditingUrlIndex = null; // 現在編集中のURL行インデックス
let nextUrlIndex = 1; // 次に追加するURL行のインデックス

// 初期化
document.addEventListener('DOMContentLoaded', function() {
    loadCategories();
    loadSettings();
    startStatsPolling();
});

// WebSocket接続
socket.on('connect', function() {
    console.log('Connected to server');
});

socket.on('stats_update', function(stats) {
    updateSystemStats(stats.system);
    updateTokenStats(stats.token_usage);
    updateQueueStatus(stats.queue_length, stats.active_jobs, stats.concurrent_limit);
});

socket.on('job_update', function(job) {
    updateJobCard(job);
});

socket.on('job_error', function(data) {
    console.error('Job error:', data);
    alert(`❌ エラー\n\nURL: ${data.url}\n\nエラー内容: ${data.error}`);
});

// 統計情報のポーリング
function startStatsPolling() {
    setInterval(function() {
        socket.emit('request_stats');
    }, 1000);  // 1秒ごと
}

// システム統計を更新
function updateSystemStats(stats) {
    document.getElementById('cpu-usage').textContent = stats.cpu_percent.toFixed(1) + '%';
    document.getElementById('memory-usage').textContent = stats.memory_percent.toFixed(1) + '%';
    document.getElementById('memory-detail').textContent =
        `${stats.memory_used_gb} GB / ${stats.memory_total_gb} GB`;
}

// トークン統計を更新
function updateTokenStats(tokenUsage) {
    updateTokenPeriod('minute', tokenUsage.minute);
    updateTokenPeriod('hour', tokenUsage.hour);
    updateTokenPeriod('day', tokenUsage.day);
    updateTokenPeriod('total', tokenUsage.total);
}

function updateTokenPeriod(period, data) {
    document.getElementById(`token-${period}-count`).textContent = `${data.count}記事`;
    document.getElementById(`token-${period}-tokens`).textContent =
        `In: ${formatNumber(data.input)} / Out: ${formatNumber(data.output)}`;
    document.getElementById(`token-${period}-cost`).textContent = `$${data.cost.toFixed(4)}`;
}

function formatNumber(num) {
    if (num >= 1000000) {
        return (num / 1000000).toFixed(2) + 'M';
    } else if (num >= 1000) {
        return (num / 1000).toFixed(2) + 'K';
    }
    return num.toString();
}

// キュー状態を更新
function updateQueueStatus(queueLength, activeJobs, concurrentLimit) {
    document.getElementById('queue-length').textContent = `${queueLength}件`;
    document.getElementById('processing-status').textContent = `${activeJobs}/${concurrentLimit}`;
}

// カテゴリを読み込み
async function loadCategories() {
    try {
        const response = await fetch('/api/categories');
        const data = await response.json();

        if (data.success) {
            categories = data.categories;
            renderCategoryTree();
        }
    } catch (error) {
        console.error('Failed to load categories:', error);
    }
}

// カテゴリツリーを描画
function renderCategoryTree() {
    const container = document.getElementById('category-tree');
    container.innerHTML = '';

    categories.forEach(cat => {
        renderCategoryItem(cat, container, 0);
    });
}

function renderCategoryItem(cat, container, level) {
    const div = document.createElement('div');
    div.className = 'category-item';
    div.style.marginLeft = `${level * 20}px`;
    div.textContent = cat.name;
    div.dataset.categoryId = cat.id;

    if (selectedCategoryIds.includes(cat.id)) {
        div.classList.add('selected');
    }

    div.onclick = function(e) {
        e.stopPropagation();
        toggleCategory(cat.id);
    };

    container.appendChild(div);

    if (cat.children && cat.children.length > 0) {
        cat.children.forEach(child => {
            renderCategoryItem(child, container, level + 1);
        });
    }
}

// カテゴリ選択をトグル
function toggleCategory(categoryId) {
    const index = selectedCategoryIds.indexOf(categoryId);

    if (index > -1) {
        selectedCategoryIds.splice(index, 1);
    } else {
        selectedCategoryIds.push(categoryId);
    }

    renderCategoryTree();
    updateSelectedCategoriesDisplay();
}

// 選択中カテゴリの表示を更新
function updateSelectedCategoriesDisplay() {
    const container = document.getElementById('selected-categories');

    if (selectedCategoryIds.length === 0) {
        container.textContent = 'なし';
        return;
    }

    const names = selectedCategoryIds.map(id => {
        const cat = findCategoryById(id, categories);
        return cat ? cat.name : id;
    });

    container.textContent = names.join(', ');
}

function findCategoryById(id, cats) {
    for (let cat of cats) {
        if (cat.id === id) return cat;
        if (cat.children && cat.children.length > 0) {
            const found = findCategoryById(id, cat.children);
            if (found) return found;
        }
    }
    return null;
}

// カテゴリモードの切り替え
function toggleCategoryMode() {
    const mode = document.querySelector('input[name="category-mode"]:checked').value;
    const selection = document.getElementById('category-selection');

    if (mode === 'manual') {
        selection.style.display = 'block';
    } else {
        selection.style.display = 'none';
    }
}

// URL入力欄を追加
function addUrlInput() {
    const container = document.getElementById('url-inputs');
    const row = document.createElement('div');
    row.className = 'url-input-row';
    row.setAttribute('data-url-index', nextUrlIndex);
    row.innerHTML = `
        <input type="text" class="url-input" placeholder="https://tabelog.com/...">
        <button onclick="openCategoryModal(this)" class="btn btn-category" title="このURLのカテゴリを設定">📁</button>
        <button onclick="removeUrlInput(this)" class="btn btn-remove">削除</button>
        <span class="url-category-label"></span>
    `;
    container.appendChild(row);
    nextUrlIndex++;
}

// URL入力欄を削除
function removeUrlInput(button) {
    const row = button.parentElement;
    const urlIndex = row.getAttribute('data-url-index');

    // カテゴリデータも削除
    if (urlIndex && urlCategoryData[urlIndex]) {
        delete urlCategoryData[urlIndex];
    }

    row.remove();
}

// 設定を読み込み
async function loadSettings() {
    try {
        const response = await fetch('/api/settings');
        const data = await response.json();

        if (data.success) {
            document.getElementById('articles-per-hour').value = data.settings.articles_per_hour;
            document.getElementById('concurrent-jobs').value = data.settings.concurrent_jobs || 3;
            document.getElementById('auto-publish').checked = data.settings.auto_publish;
        }
    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

// 設定を保存
async function saveSettings() {
    const articlesPerHour = parseInt(document.getElementById('articles-per-hour').value);
    const concurrentJobs = parseInt(document.getElementById('concurrent-jobs').value);
    const autoPublish = document.getElementById('auto-publish').checked;

    try {
        const response = await fetch('/api/settings', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                articles_per_hour: articlesPerHour,
                concurrent_jobs: concurrentJobs,
                auto_publish: autoPublish
            })
        });

        const data = await response.json();

        if (data.success) {
            alert('設定を保存しました');
        } else {
            alert('設定の保存に失敗しました: ' + data.error);
        }
    } catch (error) {
        alert('設定の保存に失敗しました: ' + error.message);
    }
}

// ジョブを送信
async function submitJobs() {
    const rows = document.querySelectorAll('.url-input-row');
    const urls = [];

    rows.forEach(row => {
        const input = row.querySelector('.url-input');
        const url = input.value.trim();
        if (url) {
            const urlIndex = row.getAttribute('data-url-index');
            const urlCategoryIds = urlCategoryData[urlIndex] || [];

            urls.push({
                url: url,
                category_ids: urlCategoryIds.length > 0 ? urlCategoryIds : null
            });
        }
    });

    if (urls.length === 0) {
        alert('URLを入力してください');
        return;
    }

    const mode = document.querySelector('input[name="category-mode"]:checked').value;
    const useAutoCategory = (mode === 'auto');

    // 全ページ処理のチェックボックスの値を取得
    const includeAllPages = document.getElementById('include-all-pages').checked;

    const requestData = {
        urls: urls,
        category_ids: selectedCategoryIds, // グローバル設定（手動選択モード時）
        use_auto_category: useAutoCategory,
        include_all_pages: includeAllPages
    };

    try {
        const response = await fetch('/api/submit', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(requestData)
        });

        const data = await response.json();

        if (data.success) {
            alert(`${data.job_ids.length}件のジョブを送信しました`);

            // URL入力欄をクリア
            rows.forEach(row => {
                const input = row.querySelector('.url-input');
                if (input) {
                    input.value = '';
                }
            });

            // URL個別カテゴリデータをクリア
            urlCategoryData = {};

            // ジョブカードを初期化
            data.job_ids.forEach(jobId => {
                jobs[jobId] = {
                    job_id: jobId,
                    status: 'queued',
                    progress: 0
                };
                addJobCard(jobs[jobId]);
            });
        } else {
            alert('ジョブの送信に失敗しました: ' + data.error);
        }
    } catch (error) {
        alert('ジョブの送信に失敗しました: ' + error.message);
    }
}

// ジョブカードを追加
function addJobCard(job) {
    const container = document.getElementById('jobs-list');

    // 空メッセージを削除
    const emptyMsg = container.querySelector('.empty-message');
    if (emptyMsg) {
        emptyMsg.remove();
    }

    const card = document.createElement('div');
    card.className = `job-card ${job.status}`;
    card.id = `job-${job.job_id}`;
    card.innerHTML = `
        <div class="job-url">${job.url || ''}</div>
        <div class="job-status">${getStatusText(job.status)}: ${job.current_step || ''}</div>
        <div class="job-progress">
            <div class="job-progress-bar" style="width: ${job.progress}%"></div>
        </div>
        <div class="job-result" style="display: none;"></div>
        <div class="job-error" style="display: none;"></div>
    `;

    container.insertBefore(card, container.firstChild);
}

// ジョブカードを更新
function updateJobCard(job) {
    jobs[job.job_id] = job;

    let card = document.getElementById(`job-${job.job_id}`);

    if (!card) {
        addJobCard(job);
        card = document.getElementById(`job-${job.job_id}`);
    }

    card.className = `job-card ${job.status}`;
    card.querySelector('.job-status').textContent = `${getStatusText(job.status)}: ${job.current_step || ''}`;
    card.querySelector('.job-progress-bar').style.width = `${job.progress}%`;

    const resultDiv = card.querySelector('.job-result');
    const errorDiv = card.querySelector('.job-error');

    if (job.status === 'completed' && job.result) {
        resultDiv.style.display = 'block';
        resultDiv.innerHTML = `
            <strong>完了:</strong> ${job.result.restaurant_name}<br>
            投稿ID: ${job.result.post_id}<br>
            <a href="${job.result.post_url}" target="_blank">投稿を確認</a>
        `;
    }

    if (job.status === 'error' && job.error) {
        errorDiv.style.display = 'block';
        errorDiv.textContent = `エラー: ${job.error}`;
    }
}

function getStatusText(status) {
    const statusMap = {
        'queued': '待機中',
        'processing': '処理中',
        'completed': '完了',
        'error': 'エラー'
    };
    return statusMap[status] || status;
}

// URLごとのカテゴリ設定モーダルを開く
function openCategoryModal(button) {
    const row = button.parentElement;
    const urlIndex = row.getAttribute('data-url-index');
    currentEditingUrlIndex = urlIndex;

    // モーダルを表示
    const modal = document.getElementById('category-modal');
    modal.style.display = 'block';

    // カテゴリツリーを描画
    renderCategoryTreeModal();
}

// モーダルを閉じる
function closeCategoryModal() {
    const modal = document.getElementById('category-modal');
    modal.style.display = 'none';
    currentEditingUrlIndex = null;
}

// モーダル内にカテゴリツリーを描画
function renderCategoryTreeModal() {
    const container = document.getElementById('category-tree-modal');
    container.innerHTML = '';

    if (categories.length === 0) {
        container.innerHTML = '<p>カテゴリが見つかりません</p>';
        return;
    }

    categories.forEach(cat => {
        renderCategoryItemModal(cat, container, 0);
    });
}

function renderCategoryItemModal(cat, container, level) {
    const item = document.createElement('div');
    item.className = 'category-item';
    item.style.marginLeft = (level * 20) + 'px';

    const currentCategories = urlCategoryData[currentEditingUrlIndex] || [];
    const isSelected = currentCategories.includes(cat.id);

    if (isSelected) {
        item.classList.add('selected');
    }

    item.innerHTML = `
        <span class="category-name">${cat.name}</span>
        ${cat.count !== undefined ? `<span class="category-count">(${cat.count})</span>` : ''}
    `;

    item.onclick = function(e) {
        e.stopPropagation();
        toggleCategoryInModal(cat.id);
    };

    container.appendChild(item);

    // 子カテゴリを再帰的に描画
    if (cat.children && cat.children.length > 0) {
        cat.children.forEach(child => {
            renderCategoryItemModal(child, container, level + 1);
        });
    }
}

function toggleCategoryInModal(categoryId) {
    if (!currentEditingUrlIndex) return;

    if (!urlCategoryData[currentEditingUrlIndex]) {
        urlCategoryData[currentEditingUrlIndex] = [];
    }

    const categories = urlCategoryData[currentEditingUrlIndex];
    const index = categories.indexOf(categoryId);

    if (index > -1) {
        // 既に選択されている場合は削除
        categories.splice(index, 1);
    } else {
        // 選択されていない場合は追加
        categories.push(categoryId);
    }

    // モーダルを再描画
    renderCategoryTreeModal();

    // URL行のラベルを更新
    updateUrlCategoryLabel(currentEditingUrlIndex);
}

function updateUrlCategoryLabel(urlIndex) {
    const row = document.querySelector(`.url-input-row[data-url-index="${urlIndex}"]`);
    if (!row) return;

    const label = row.querySelector('.url-category-label');
    const categoryIds = urlCategoryData[urlIndex] || [];

    if (categoryIds.length === 0) {
        label.textContent = '';
        return;
    }

    const names = categoryIds.map(id => {
        const cat = findCategoryById(id, categories);
        return cat ? cat.name : id;
    });

    label.textContent = `📁 ${names.join(', ')}`;
}

function clearUrlCategories() {
    if (currentEditingUrlIndex) {
        urlCategoryData[currentEditingUrlIndex] = [];
        renderCategoryTreeModal();
        updateUrlCategoryLabel(currentEditingUrlIndex);
    }
}

// モーダル外をクリックで閉じる
window.onclick = function(event) {
    const modal = document.getElementById('category-modal');
    if (event.target === modal) {
        closeCategoryModal();
    }
}
