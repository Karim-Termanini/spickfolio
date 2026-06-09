// Shared application state
// --- State Variables ---
let currentTab = 'cheat-tab';
let activeSource = 'all';
let datasetsList = [];
let selectedDataset = null;
let activeCodeTab = 'r'; // 'r' or 'py'
let searchDebounceTimer = null;
let currentLang = localStorage.getItem('app_lang') || 'de';
const searchCache = {};
const SEARCH_CACHE_TTL_MS = {
    rdatasets: 60 * 60 * 1000,
    huggingface: 5 * 60 * 1000,
    kaggle: 5 * 60 * 1000,
    all: 5 * 60 * 1000,
};

function getSearchCacheEntry(cacheKey) {
    const entry = searchCache[cacheKey];
    if (!entry) return null;
    const ttl = SEARCH_CACHE_TTL_MS[activeSource] ?? SEARCH_CACHE_TTL_MS.all;
    if (Date.now() - entry.cachedAt > ttl) {
        delete searchCache[cacheKey];
        return null;
    }
    return entry.data;
}

function setSearchCacheEntry(cacheKey, data) {
    searchCache[cacheKey] = { data, cachedAt: Date.now() };
}

let cheatSheetData = [];
