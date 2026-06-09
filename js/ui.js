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
let currentTheme = 'dark';

function applyTheme(theme) {
    currentTheme = theme === 'light' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', currentTheme);
    try {
        localStorage.setItem(THEME_STORAGE_KEY, currentTheme);
    } catch (e) {}
    updateThemeToggleButton();
}

function updateThemeToggleButton() {
    if (!themeToggleBtn) return;
    const trans = uiTranslations[currentLang] || {};
    if (currentTheme === 'light') {
        themeToggleBtn.title = trans.themeSwitchToDark || 'Switch to dark mode';
    } else {
        themeToggleBtn.title = trans.themeSwitchToLight || 'Switch to light mode';
    }
    themeToggleBtn.setAttribute('aria-label', themeToggleBtn.title);
}

function initTheme() {
    let stored = 'dark';
    try {
        stored = localStorage.getItem(THEME_STORAGE_KEY) || 'dark';
    } catch (e) {}
    applyTheme(stored);
    if (themeToggleBtn) {
        themeToggleBtn.addEventListener('click', () => {
            applyTheme(currentTheme === 'light' ? 'dark' : 'light');
        });
    }
}
// --- Close button & Esc key ---
if (closeBtn) {
    closeBtn.addEventListener('click', () => window.close());
}
window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        window.close();
    }
});

// --- Back Button ---
if (backToSearchBtn) {
    backToSearchBtn.addEventListener('click', () => {
        detailView.style.display = 'none';
        searchView.style.display = 'flex';
        selectedDataset = null;
        document.querySelectorAll('.dataset-item-card').forEach(c => c.classList.remove('active'));
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
            // Return to search list from detail view on tab click
            detailView.style.display = 'none';
            searchView.style.display = 'flex';
            selectedDataset = null;
            currentPage = 1;
            triggerSearch();
        }
    });
});
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
}

// --- Header Search Bar Handler ---
searchInput.addEventListener('input', () => {
    const query = searchInput.value.toLowerCase().trim();
    if (currentTab === 'cheat-tab') {
        filterCheatSheet(query);
    } else {
        clearTimeout(searchDebounceTimer);
        currentPage = 1;
        searchDebounceTimer = setTimeout(() => {
            triggerSearch(query, 1);
        }, 300);
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
