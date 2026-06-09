// Server connection and config
// API base URL — same-origin when served by server.py, else localhost + port
let API_BASE = 'http://127.0.0.1:18700';
const explicitPort = new URLSearchParams(window.location.search).get('port');
const servedFromServer = window.location.protocol.startsWith('http') &&
    (window.location.hostname === '127.0.0.1' || window.location.hostname === 'localhost');

if (servedFromServer) {
    API_BASE = window.location.origin;
} else if (explicitPort) {
    API_BASE = `http://127.0.0.1:${explicitPort}`;
}

// Whether R is available on the server (for RData/RDS export)
let rAvailable = false;
let parquetAvailable = false;
let kaggleAuthAvailable = false;
let rdatasetsCachedAt = null;
let xdgDownloadsDir = '~/Downloads';
let xdgDocumentsDir = '~/Documents';
let serverConnected = false;

function updateParquetBanner() {
    const banner = document.getElementById('parquetSetupBanner');
    if (banner) banner.style.display = parquetAvailable ? 'none' : 'block';
}

function updateKaggleBanner() {
    if (!kaggleBanner) return;
    if (kaggleAuthAvailable) {
        kaggleBanner.style.display = 'none';
        return;
    }
    kaggleBanner.style.display = activeSource === 'kaggle' ? 'block' : 'none';
}

function showKaggleSetupBanner() {
    if (kaggleBanner && !kaggleAuthAvailable) {
        kaggleBanner.style.display = 'block';
    }
}

function recheckKaggleAuth() {
    const trans = uiTranslations[currentLang] || {};
    return fetch(`${API_BASE}/config`)
        .then(r => {
            if (!r.ok) throw new Error('config failed');
            return r.json();
        })
        .then(cfg => {
            kaggleAuthAvailable = !!cfg.kaggle_auth;
            updateKaggleBanner();
            if (kaggleAuthAvailable) {
                showToast(trans.kaggleAuthOk || 'Kaggle credentials found.');
                triggerSearch(searchInput.value.trim(), currentPage);
            } else {
                showToast(trans.kaggleAuthMissing || 'Kaggle credentials not found.', true);
            }
        })
        .catch(() => {
            showToast(trans.connectionError || 'Connection error.', true);
        });
}

function updateRdatasetsRefreshUI() {
    const section = document.getElementById('rdatasetsRefreshSection');
    const timeEl = document.getElementById('rdatasetsLastUpdated');
    if (!section || !timeEl) return;

    if (activeSource === 'rdatasets') {
        section.style.display = 'flex';
        if (rdatasetsCachedAt) {
            const date = new Date(rdatasetsCachedAt * 1000);
            const timeStr = date.toLocaleString(currentLang === 'ar' ? 'ar-SA' : (currentLang === 'de' ? 'de-DE' : 'en-US'), {
                day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit'
            });
            timeEl.textContent = (uiTranslations[currentLang].lastUpdated || 'Last updated: {time}').replace('{time}', timeStr);
        } else {
            timeEl.textContent = '';
        }
    } else {
        section.style.display = 'none';
    }
}

function connectToServer(baseOrPort, retries = 5) {
    const base = (typeof baseOrPort === 'string' && baseOrPort.startsWith('http'))
        ? baseOrPort
        : `http://127.0.0.1:${baseOrPort}`;
    return fetch(`${base}/config`).then(r => {
        if (!r.ok) throw new Error('not ok');
        return r.json();
    }).then(cfg => {
        API_BASE = base;
        rAvailable = cfg.r_available;
        parquetAvailable = cfg.parquet_available;
        kaggleAuthAvailable = !!cfg.kaggle_auth;
        rdatasetsCachedAt = cfg.rdatasets_cached_at;
        if (cfg.downloads_dir) xdgDownloadsDir = cfg.downloads_dir;
        if (cfg.documents_dir) xdgDocumentsDir = cfg.documents_dir;
        updateParquetBanner();
        updateKaggleBanner();
        updateRdatasetsRefreshUI();
        serverConnected = true;
    }).catch(err => {
        if (retries > 0) {
            return new Promise(resolve => setTimeout(resolve, 300))
                .then(() => connectToServer(baseOrPort, retries - 1));
        }
        throw err;
    });
}

function isAppWindow() {
    return window.matchMedia('(display-mode: standalone)').matches ||
        window.matchMedia('(display-mode: minimal-ui)').matches;
}

function applyLaunchModeUi() {
    if (servedFromServer && !isAppWindow()) {
        document.body.classList.add('standalone-tab');
        if (closeBtn) closeBtn.style.display = 'none';
    }
}

function getServerBase() {
    if (servedFromServer) return window.location.origin;
    if (explicitPort) return explicitPort;
    return 18700;
}

function retryServerConnection() {
    return connectToServer(getServerBase())
        .then(() => Promise.all([
            loadTranslations(currentLang),
            loadCheatSheetData(),
        ]))
        .then(() => {
            applyTranslations(currentLang);
            if (currentTab === 'datasets-tab') triggerSearch();
        });
}

function showAppConnectionError() {
    serverConnected = false;
    const retry = () => retryServerConnection().catch(() => showAppConnectionError());
    const cheatGrid = document.querySelector('.cheat-sheet-grid');
    if (cheatGrid) renderConnectionErrorState(cheatGrid, retry);
    const listPane = document.getElementById('datasetsList');
    if (listPane) renderConnectionErrorState(listPane, retry);
}

// Initial connection and data load
function initializeApp(baseOrPort) {
    connectToServer(baseOrPort)
        .then(() => {
            // Server connected! Now load everything else.
            return Promise.all([
                loadTranslations(currentLang),
                loadCheatSheetData()
            ]);
        })
        .then(() => {
            applyTranslations(currentLang);
            if (currentTab === 'datasets-tab') triggerSearch();
        })
        .catch(() => {
            showAppConnectionError();
        });
}
// Install pyarrow button
const installPyarrowBtn = document.getElementById('installPyarrowBtn');
if (installPyarrowBtn) {
    installPyarrowBtn.addEventListener('click', () => {
        if (installPyarrowBtn.disabled) return;
        installPyarrowBtn.disabled = true;
        const trans = uiTranslations[currentLang] || {};
        installPyarrowBtn.textContent = trans.installing || 'Installing...';
        fetch(`${API_BASE}/install_pyarrow`, { method: 'POST' })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    installPyarrowBtn.textContent = trans.installed || 'Installed!';
                    parquetAvailable = true;
                    updateParquetBanner();
                    showToast(trans.parquetInstalled || 'pyarrow installed — Parquet support is now available.');
                } else {
                    installPyarrowBtn.textContent = trans.installFailed || 'Install failed';
                    showToast(data.error || (trans.installFailed || 'Installation failed.'), true);
                    setTimeout(() => { installPyarrowBtn.disabled = false; installPyarrowBtn.textContent = 'Install pyarrow'; }, 5000);
                }
            })
            .catch(() => {
                installPyarrowBtn.textContent = trans.installFailed || 'Install failed';
                showToast(trans.connectionError, true);
                setTimeout(() => { installPyarrowBtn.disabled = false; installPyarrowBtn.textContent = 'Install pyarrow'; }, 5000);
            });
    });
}

// Refresh Rdatasets button
const refreshRdatasetsBtn = document.getElementById('refreshRdatasetsBtn');
if (refreshRdatasetsBtn) {
    refreshRdatasetsBtn.addEventListener('click', () => {
        if (refreshRdatasetsBtn.disabled) return;
        refreshRdatasetsBtn.disabled = true;
        
        const trans = uiTranslations[currentLang] || {};
        showToast(trans.refreshing || 'Refreshing...');
        
        fetch(`${API_BASE}/refresh_rdatasets`, { method: 'POST' })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    rdatasetsCachedAt = data.cached_at;
                    updateRdatasetsRefreshUI();
                    showToast(trans.refreshed || 'Catalog Updated');
                    
                    // Clear search cache for rdatasets to force reload
                    Object.keys(searchCache).forEach(key => {
                        if (key.includes(':rdatasets:')) delete searchCache[key];
                    });
                    
                    if (activeSource === 'rdatasets') triggerSearch(searchInput.value);
                } else {
                    showToast(data.error || 'Refresh failed', true);
                }
            })
            .catch(err => {
                showToast(trans.connectionError, true);
                console.error(err);
            })
            .finally(() => {
                refreshRdatasetsBtn.disabled = false;
            });
    });
}
// Heartbeat — keeps server alive while this window is open
function startHeartbeat() {
    function beat() {
        fetch(`${API_BASE}/heartbeat`).catch(() => {});
    }
    beat();
    setInterval(beat, 10000);
}
