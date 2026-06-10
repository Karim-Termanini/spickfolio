// Keyboard navigation and global shortcuts
function getDatasetCards() {
    const listPane = document.getElementById('datasetsList');
    return listPane ? [...listPane.querySelectorAll('.dataset-item-card')] : [];
}

function focusDatasetCardAtIndex(index) {
    const cards = getDatasetCards();
    if (!cards.length || index < 0 || index >= cards.length) return false;
    cards.forEach((c, i) => {
        c.setAttribute('tabindex', i === index ? '0' : '-1');
        c.setAttribute('aria-selected', i === index ? 'true' : 'false');
    });
    cards[index].focus({ preventScroll: false });
    return true;
}

function focusDatasetCardById(datasetId) {
    if (!datasetId) return focusDatasetCardAtIndex(0);
    const cards = getDatasetCards();
    const idx = cards.findIndex(c => c.dataset.datasetId === datasetId);
    return focusDatasetCardAtIndex(idx >= 0 ? idx : 0);
}

function requestDatasetListFocus(index = 0) {
    datasetListFocusPending = true;
    datasetListFocusIndex = index;
}

function initDatasetCardTabindex() {
    getDatasetCards().forEach((c, i) => {
        c.setAttribute('tabindex', i === 0 ? '0' : '-1');
        c.setAttribute('aria-selected', 'false');
    });
}

function applyDatasetListFocusIfPending() {
    if (!datasetListFocusPending) return;
    datasetListFocusPending = false;
    focusDatasetCardAtIndex(datasetListFocusIndex);
}

function updateDatasetListA11y() {
    const listPane = document.getElementById('datasetsList');
    if (!listPane) return;
    const trans = uiTranslations[currentLang] || {};
    listPane.setAttribute('aria-label', trans.datasetListLabel || 'Dataset results');
}

function syncFilterPillTabindex() {
    document.querySelectorAll('.filter-pill').forEach(pill => {
        pill.setAttribute('tabindex', pill.classList.contains('active') ? '0' : '-1');
    });
}

function activateNavTab(tabId) {
    const tab = document.querySelector(`.nav-tab[data-tab="${tabId}"]`);
    if (tab) tab.click();
}

function getCheatCopyables() {
    const grid = document.querySelector('.cheat-sheet-grid');
    if (!grid) return [];
    return [...grid.querySelectorAll('.copyable')].filter(el => {
        let node = el.closest('.cheat-card');
        return node && node.style.display !== 'none';
    });
}

function focusCheatCopyableAtIndex(index) {
    const items = getCheatCopyables();
    if (!items.length || index < 0 || index >= items.length) return false;
    items.forEach((el, i) => {
        el.setAttribute('tabindex', i === index ? '0' : '-1');
    });
    items[index].focus({ preventScroll: false });
    return true;
}

function initCheatSheetCopyableTabindex() {
    const trans = uiTranslations[currentLang] || {};
    const label = trans.copyCodeLabel || 'Copy code snippet';
    getCheatCopyables().forEach((el, i) => {
        el.setAttribute('tabindex', i === 0 ? '0' : '-1');
        el.setAttribute('role', 'button');
        el.setAttribute('aria-label', label);
    });
}

function updateCheatSheetA11y() {
    const grid = document.querySelector('.cheat-sheet-grid');
    if (!grid) return;
    const trans = uiTranslations[currentLang] || {};
    grid.setAttribute('aria-label', trans.cheatSheetLabel || 'Cheat sheet');
    initCheatSheetCopyableTabindex();
}

function setupCheatSheetKeyboard() {
    const grid = document.querySelector('.cheat-sheet-grid');
    if (!grid || grid.dataset.kbBound) return;
    grid.dataset.kbBound = '1';

    grid.addEventListener('keydown', (e) => {
        if (currentTab !== 'cheat-tab') return;
        const item = e.target.closest('.copyable');
        if (!item) return;
        const items = getCheatCopyables();
        const idx = items.indexOf(item);
        if (idx < 0) return;

        switch (e.key) {
            case 'ArrowDown':
            case 'ArrowRight':
                e.preventDefault();
                focusCheatCopyableAtIndex(idx + 1);
                break;
            case 'ArrowUp':
            case 'ArrowLeft':
                e.preventDefault();
                focusCheatCopyableAtIndex(idx - 1);
                break;
            case 'Home':
                e.preventDefault();
                focusCheatCopyableAtIndex(0);
                break;
            case 'End':
                e.preventDefault();
                focusCheatCopyableAtIndex(items.length - 1);
                break;
            case 'Enter':
            case ' ':
                e.preventDefault();
                item.click();
                break;
        }
    });
}

function setupDatasetListKeyboard() {
    const listPane = document.getElementById('datasetsList');
    if (!listPane || listPane.dataset.kbBound) return;
    listPane.dataset.kbBound = '1';

    listPane.addEventListener('keydown', (e) => {
        const card = e.target.closest('.dataset-item-card');
        if (!card) return;
        const cards = getDatasetCards();
        const idx = cards.indexOf(card);

        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                focusDatasetCardAtIndex(idx + 1);
                break;
            case 'ArrowUp':
                e.preventDefault();
                focusDatasetCardAtIndex(idx - 1);
                break;
            case 'Home':
                e.preventDefault();
                focusDatasetCardAtIndex(0);
                break;
            case 'End':
                e.preventDefault();
                focusDatasetCardAtIndex(cards.length - 1);
                break;
            case 'PageDown':
                e.preventDefault();
                focusDatasetCardAtIndex(Math.min(idx + 5, cards.length - 1));
                break;
            case 'PageUp':
                e.preventDefault();
                focusDatasetCardAtIndex(Math.max(idx - 5, 0));
                break;
            case 'ArrowRight':
                if (idx === cards.length - 1 && currentPage < totalPages) {
                    e.preventDefault();
                    requestDatasetListFocus(0);
                    triggerSearch(searchInput.value.trim(), currentPage + 1);
                }
                break;
            case 'ArrowLeft':
                if (idx === 0 && currentPage > 1) {
                    e.preventDefault();
                    requestDatasetListFocus(0);
                    triggerSearch(searchInput.value.trim(), currentPage - 1);
                }
                break;
            case 'Enter':
            case ' ':
                e.preventDefault();
                card.click();
                break;
        }
    });
}

function setupFilterPillKeyboard() {
    const bar = document.querySelector('.datasets-filter-bar');
    if (!bar || bar.dataset.kbBound) return;
    bar.dataset.kbBound = '1';

    syncFilterPillTabindex();

    bar.addEventListener('keydown', (e) => {
        const pill = e.target.closest('.filter-pill');
        if (!pill) return;
        const pills = [...bar.querySelectorAll('.filter-pill')];
        const idx = pills.indexOf(pill);

        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
            e.preventDefault();
            pills[Math.min(idx + 1, pills.length - 1)].focus();
        } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
            e.preventDefault();
            pills[Math.max(idx - 1, 0)].focus();
        } else if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            pill.click();
        }
    });
}

function setupSearchKeyboard() {
    if (!searchInput || searchInput.dataset.kbBound) return;
    searchInput.dataset.kbBound = '1';

    searchInput.addEventListener('keydown', (e) => {
        if (e.key !== 'ArrowDown') return;
        if (currentTab === 'datasets-tab') {
            if (!getDatasetCards().length) return;
            e.preventDefault();
            focusDatasetCardAtIndex(0);
            return;
        }
        if (currentTab === 'cheat-tab') {
            if (!getCheatCopyables().length) return;
            e.preventDefault();
            focusCheatCopyableAtIndex(0);
        }
    });
}

function initKeyboardNav() {
    setupCheatSheetKeyboard();
    setupDatasetListKeyboard();
    setupFilterPillKeyboard();
    setupSearchKeyboard();
    updateDatasetListA11y();
    updateCheatSheetA11y();

    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (typeof isDownloadCompleteModalOpen === 'function' && isDownloadCompleteModalOpen()) {
                e.preventDefault();
                closeDownloadCompleteModal();
                return;
            }
            if (detailView && detailView.style.display !== 'none') {
                e.preventDefault();
                backToSearchBtn?.click();
                return;
            }
            closeAppWindow();
            return;
        }

        if (e.ctrlKey && e.shiftKey && e.key.toLowerCase() === 't' && !isEditableTarget(e.target)) {
            e.preventDefault();
            cycleTheme();
            return;
        }

        if (e.ctrlKey && !e.shiftKey && e.key === '1') {
            e.preventDefault();
            activateNavTab('cheat-tab');
            return;
        }
        if (e.ctrlKey && !e.shiftKey && e.key === '2') {
            e.preventDefault();
            activateNavTab('datasets-tab');
            return;
        }

        if (isEditableTarget(e.target)) return;

        if (e.key === '/') {
            e.preventDefault();
            searchInput?.focus();
            searchInput?.select();
        }
    });
}
