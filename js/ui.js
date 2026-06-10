// DOM refs, toast, clipboard, tabs, search
// --- DOM Elements ---
const tabs = document.querySelectorAll('.nav-tab');
const contents = document.querySelectorAll('.tab-content');
const searchInput = document.getElementById('searchInput');
const closeBtn = document.getElementById('closeBtn');
const toast = document.getElementById('toast');

const searchView = document.getElementById('datasetSearchView');
const detailView = document.getElementById('datasetDetailView');
const detailContent = document.getElementById('datasetDetailContent');
const backToSearchBtn = document.getElementById('backToSearchBtn');
const kaggleBanner = document.getElementById('kaggleSetupBanner');
const languageSelect = document.getElementById('languageSelect');
const themeToggleBtn = document.getElementById('themeToggleBtn');
const overlayContainer = document.getElementById('overlayContainer');

const THEME_STORAGE_KEY = 'app_theme';
let currentTheme = 'system';
let systemThemeMedia = null;

function getSystemTheme() {
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
}

function getEffectiveTheme(mode) {
    const m = mode || currentTheme;
    return m === 'system' ? getSystemTheme() : m;
}

function applyTheme(theme) {
    currentTheme = (theme === 'light' || theme === 'dark' || theme === 'system') ? theme : 'system';
    const effective = getEffectiveTheme(currentTheme);
    document.documentElement.setAttribute('data-theme-mode', currentTheme);
    if (effective === 'light') {
        document.documentElement.setAttribute('data-theme', 'light');
    } else {
        document.documentElement.removeAttribute('data-theme');
    }
    try {
        localStorage.setItem(THEME_STORAGE_KEY, currentTheme);
    } catch (e) {}
    updateThemeToggleButton();
}

function updateThemeToggleButton() {
    if (!themeToggleBtn) return;
    const trans = uiTranslations[currentLang] || {};
    let label;
    if (currentTheme === 'light') {
        label = trans.themeSwitchToSystem || 'Use system theme';
    } else if (currentTheme === 'system') {
        label = trans.themeSwitchToDark || 'Switch to dark mode';
    } else {
        label = trans.themeSwitchToLight || 'Switch to light mode';
    }
    themeToggleBtn.title = label;
    themeToggleBtn.setAttribute('aria-label', label);
}

function cycleTheme() {
    if (currentTheme === 'dark') applyTheme('light');
    else if (currentTheme === 'light') applyTheme('system');
    else applyTheme('dark');
    showThemeChangeToast();
}

function showThemeChangeToast() {
    const trans = uiTranslations[currentLang] || {};
    let msg;
    if (currentTheme === 'dark') msg = trans.themeChangedDark || 'Dark mode';
    else if (currentTheme === 'light') msg = trans.themeChangedLight || 'Light mode';
    else msg = trans.themeChangedSystem || 'System theme';
    showToast(msg);
}

function isEditableTarget(el) {
    if (!el) return false;
    const tag = el.tagName;
    return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable;
}

function initTheme() {
    let stored = 'system';
    try {
        stored = localStorage.getItem(THEME_STORAGE_KEY) || 'system';
    } catch (e) {}
    applyTheme(stored);

    systemThemeMedia = window.matchMedia('(prefers-color-scheme: dark)');
    systemThemeMedia.addEventListener('change', () => {
        if (currentTheme === 'system') {
            applyTheme('system');
        }
    });

    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', cycleTheme);
    }
}
// --- Close button ---
if (closeBtn) {
    closeBtn.addEventListener('click', () => window.close());
}

// --- Back Button ---
if (backToSearchBtn) {
    backToSearchBtn.addEventListener('click', () => {
        const prevId = selectedDataset?.id;
        detailView.style.display = 'none';
        searchView.style.display = 'flex';
        selectedDataset = null;
        document.querySelectorAll('.dataset-item-card').forEach(c => c.classList.remove('active'));
        if (typeof renderDownloadHistoryPanel === 'function') renderDownloadHistoryPanel();
        if (prevId) focusDatasetCardById(prevId);
    });
}

// --- Tab Switching Logic ---
tabs.forEach(tab => {
    tab.addEventListener('click', () => {
        tabs.forEach(t => t.classList.remove('active'));
        contents.forEach(c => c.classList.remove('active'));
        
        tab.classList.add('active');
        const targetTab = document.getElementById(tab.dataset.tab);
        targetTab.classList.add('active');

        currentTab = tab.dataset.tab;
        searchInput.value = '';
        
        if (currentTab === 'cheat-tab') {
            document.querySelectorAll('.cheat-card').forEach(card => {
                card.style.display = 'flex';
            });
        } else if (currentTab === 'datasets-tab') {
            detailView.style.display = 'none';
            searchView.style.display = 'flex';
            selectedDataset = null;
            currentPage = 1;
            requestDatasetListFocus(0);
            triggerSearch();
        }
    });
});
// --- Download complete modal (persistent until dismissed) ---
let downloadCompleteOnClose = null;

function isDownloadCompleteModalOpen() {
    const modal = document.getElementById('downloadCompleteModal');
    return modal && !modal.hidden;
}

function closeDownloadCompleteModal() {
    const modal = document.getElementById('downloadCompleteModal');
    if (!modal || modal.hidden) return;
    modal.hidden = true;
    document.body.classList.remove('download-complete-open');
    const cb = downloadCompleteOnClose;
    downloadCompleteOnClose = null;
    if (typeof cb === 'function') cb();
}

function showDownloadCompleteModal({ filePath, pathIsDir, onClose } = {}) {
    const modal = document.getElementById('downloadCompleteModal');
    if (!modal) return;

    const trans = uiTranslations[currentLang] || {};
    downloadCompleteOnClose = onClose || null;

    const titleEl = document.getElementById('downloadCompleteTitle');
    const pathLabelEl = document.getElementById('downloadCompletePathLabel');
    const pathEl = document.getElementById('downloadCompletePath');
    const openFileBtn = document.getElementById('downloadCompleteOpenFile');
    const openFolderBtn = document.getElementById('downloadCompleteOpenFolder');
    const dismissBtn = document.getElementById('downloadCompleteDismiss');
    const closeBtn = document.getElementById('downloadCompleteCloseBtn');

    if (titleEl) {
        titleEl.textContent = trans.downloadCompleteTitle || trans.toastSuccess || 'Download complete';
    }
    if (pathLabelEl) {
        pathLabelEl.textContent = trans.downloadCompletePathLabel || 'Saved to';
    }
    if (pathEl) {
        pathEl.textContent = filePath || '';
    }
    if (openFileBtn) {
        openFileBtn.textContent = trans.downloadOpenFileBtn || 'Open file';
        openFileBtn.hidden = !!pathIsDir;
        openFileBtn.onclick = () => {
            if (typeof openFileOnDesktop === 'function') openFileOnDesktop(filePath);
        };
    }
    if (openFolderBtn) {
        openFolderBtn.textContent = trans.downloadShowFolderBtn || 'Show in folder';
        openFolderBtn.onclick = () => {
            if (typeof openPathInFileManager === 'function') openPathInFileManager(filePath);
        };
    }
    const closeLabel = trans.downloadCompleteClose || 'Close';
    if (dismissBtn) {
        dismissBtn.textContent = closeLabel;
        dismissBtn.onclick = () => closeDownloadCompleteModal();
    }
    if (closeBtn) {
        closeBtn.setAttribute('aria-label', closeLabel);
        closeBtn.onclick = () => closeDownloadCompleteModal();
    }

    modal.hidden = false;
    document.body.classList.add('download-complete-open');
    (dismissBtn || openFolderBtn || openFileBtn)?.focus();
}

// --- Toast Notifications ---
function showToast(message, isError = false) {
    if (!toast) return;
    toast.textContent = message;
    if (isError) {
        toast.style.background = '#f38ba8'; // Catppuccin Red
        toast.style.color = '#09090d';
    } else {
        toast.style.background = '#a6e3a1'; // Catppuccin Green
        toast.style.color = '#09090d';
    }
    toast.classList.add('show');
    setTimeout(() => {
        toast.classList.remove('show');
    }, 4000);
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
    initCheatSheetCopyableTabindex();
}

// --- Header Search Bar Handler ---
if (searchInput) searchInput.addEventListener('input', () => {
    const query = searchInput.value.toLowerCase().trim();
    if (currentTab === 'cheat-tab') {
        filterCheatSheet(query);
    } else {
        clearTimeout(searchDebounceTimer);
        currentPage = 1;
        searchDebounceTimer = setTimeout(() => {
            triggerSearch(query, 1);
        }, getSearchDebounceMs());
    }
});

// --- Code Snippet Copy-to-Clipboard ---
function copyToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        return navigator.clipboard.writeText(text).catch(() => fallbackCopy(text));
    }
    return fallbackCopy(text);
}

function fallbackCopy(text) {
    return new Promise((resolve, reject) => {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.style.position = 'fixed';
        ta.style.opacity = '0';
        document.body.appendChild(ta);
        ta.select();
        try {
            document.execCommand('copy');
            resolve();
        } catch (e) {
            reject(e);
        }
        document.body.removeChild(ta);
    });
}
