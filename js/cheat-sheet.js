// Cheat sheet tab
function loadCheatSheetData() {
    // Try local file first (fastest, but might be blocked by browser)
    return fetch('cheat-sheet-data.json')
        .then(r => {
            if (!r.ok) throw new Error();
            return r.json();
        })
        .catch(() => {
            // Fallback to server API
            return fetch(`${API_BASE}/cheat-sheet`).then(r => r.json());
        })
        .then(data => {
            cheatSheetData = data;
            renderCheatSheet();
        })
        .catch(err => console.error('Failed to load cheat sheet data:', err));
}
// --- Cheat Sheet: Dynamic rendering from JSON ---
function renderCheatSheet() {
    const grid = document.querySelector('.cheat-sheet-grid');
    if (!grid || !cheatSheetData.length) return;
    grid.innerHTML = '';
    cheatSheetData.forEach(card => {
        const cardEl = document.createElement('div');
        cardEl.className = 'cheat-card' + (card.fullWidth ? ' full-width' : '');
        cardEl.dataset.tags = card.tags;

        const title = document.createElement('h3');
        title.dataset.i18n = card.i18nTitle;
        title.textContent = card.i18nTitle;
        cardEl.appendChild(title);

        if (card.blocks) {
            card.blocks.forEach(block => {
                const blockEl = document.createElement('div');
                blockEl.className = 'comparison-block';

                const sub = document.createElement('div');
                sub.className = 'card-subtitle';
                sub.dataset.i18n = block.i18nSubtitle;
                sub.textContent = block.i18nSubtitle;
                blockEl.appendChild(sub);

                const rDisplay = block.rDisplay || block.rCode;
                const pyDisplay = block.pyDisplay || block.pyCode;

                const rRow = document.createElement('div');
                rRow.className = 'lang-row';
                rRow.innerHTML = `<span class="lang-tag r-tag">R</span><code class="copyable" data-code="${escapeAttr(block.rCode)}">${escapeHtml(rDisplay)}</code>`;
                blockEl.appendChild(rRow);

                const pyRow = document.createElement('div');
                pyRow.className = 'lang-row';
                pyRow.innerHTML = `<span class="lang-tag py-tag">Python</span><code class="copyable" data-code="${escapeAttr(block.pyCode)}">${escapeHtml(pyDisplay)}</code>`;
                blockEl.appendChild(pyRow);

                cardEl.appendChild(blockEl);
            });
        }

        if (card.columns) {
            const pkgGrid = document.createElement('div');
            pkgGrid.className = 'packages-grid';
            card.columns.forEach(col => {
                const colEl = document.createElement('div');
                colEl.className = 'pkg-col';
                const header = document.createElement('h4');
                header.dataset.i18n = col.i18nHeader;
                header.textContent = col.i18nHeader;
                colEl.appendChild(header);
                const ul = document.createElement('ul');
                col.items.forEach(key => {
                    const li = document.createElement('li');
                    li.dataset.i18n = key;
                    li.textContent = key;
                    ul.appendChild(li);
                });
                colEl.appendChild(ul);
                pkgGrid.appendChild(colEl);
            });
            cardEl.appendChild(pkgGrid);
        }

        grid.appendChild(cardEl);
    });

    // Re-bind copyable click handlers
    document.querySelectorAll('.copyable').forEach(item => {
        item.addEventListener('click', () => {
            const code = item.dataset.code;
            copyToClipboard(code).then(() => {
                showToast(uiTranslations[currentLang].toastCopy);
            });
        });
    });

    // Re-apply translations
    applyTranslations(currentLang);
    // Re-filter if there's a search query
    const query = searchInput.value.toLowerCase().trim();
    if (query) filterCheatSheet(query);
}

function escapeAttr(str) {
    return str.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
// --- Spickzettel (Cheat Sheet) Filtering ---
function filterCheatSheet(query) {
    const activeTab = document.getElementById('cheat-tab');
    const cards = activeTab.querySelectorAll('.cheat-card');
    
    cards.forEach(card => {
        const tags = card.dataset.tags ? card.dataset.tags.toLowerCase() : '';
        const titleAndText = card.textContent.toLowerCase();
        
        if (titleAndText.includes(query) || tags.includes(query)) {
            card.style.display = 'flex';
        } else {
            card.style.display = 'none';
        }
    });
}
