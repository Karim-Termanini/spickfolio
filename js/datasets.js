// Dataset browser tab
function updateFavoriteButton(btn, datasetId) {
    const trans = uiTranslations[currentLang] || {};
    const fav = DatasetStorage.isFavorite(datasetId);
    btn.textContent = fav ? '★' : '☆';
    btn.classList.toggle('active', fav);
    btn.title = fav ? (trans.favoriteRemove || 'Remove from favorites') : (trans.favoriteAdd || 'Add to favorites');
}

function setupFavoriteButton(dataset) {
    const header = detailContent.querySelector('.detail-header');
    if (!header || header.querySelector('.favorite-btn')) return;
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'favorite-btn';
    btn.id = 'favoriteToggleBtn';
    updateFavoriteButton(btn, dataset.id);
    btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const added = DatasetStorage.toggleFavorite(dataset);
        updateFavoriteButton(btn, dataset.id);
        const trans = uiTranslations[currentLang] || {};
        showToast(added ? (trans.favoriteAdded || 'Added to favorites') : (trans.favoriteRemoved || 'Removed from favorites'));
        if (activeSource === 'favorites') {
            triggerSearch(searchInput.value.trim(), currentPage);
        }
    });
    header.appendChild(btn);
}
// --- Bytes Formatter ---
function formatBytes(bytes) {
    if (bytes === undefined || bytes === null || isNaN(bytes)) return '';
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function formatDownloadEta(seconds) {
    if (!seconds || seconds < 1) return '';
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    if (mins < 60) return secs ? `${mins}m ${secs}s` : `${mins}m`;
    const hours = Math.floor(mins / 60);
    const remMins = mins % 60;
    return remMins ? `${hours}h ${remMins}m` : `${hours}h`;
}

function showDownloadProgress(phase, bytesRead, bytesTotal, etaSeconds) {
    const container = document.getElementById('downloadProgress');
    const bar = document.getElementById('downloadProgressBar');
    const label = document.getElementById('downloadProgressLabel');
    const meta = document.getElementById('downloadProgressMeta');
    const cancelBtn = document.getElementById('downloadCancelBtn');
    const retryBtn = document.getElementById('downloadRetryBtn');
    const trans = uiTranslations[currentLang] || {};
    if (!container || !bar || !label || !meta) return;

    container.hidden = false;
    bar.classList.remove('complete', 'error');
    if (cancelBtn) cancelBtn.hidden = false;
    if (retryBtn) retryBtn.hidden = true;
    const showFolderBtn = document.getElementById('downloadShowFolderBtn');
    if (showFolderBtn) showFolderBtn.hidden = true;
    const openFileBtn = document.getElementById('downloadOpenFileBtn');
    if (openFileBtn) openFileBtn.hidden = true;

    if (phase === 'converting') {
        label.textContent = trans.toastConverting || 'Converting...';
        bar.classList.add('indeterminate');
        bar.style.width = '';
        meta.textContent = '';
        return;
    }

    label.textContent = trans.toastDownloading || 'Downloading...';

    if (phase === 'downloading' && bytesTotal && bytesTotal > 0) {
        bar.classList.remove('indeterminate');
        const pct = Math.min(100, Math.round((bytesRead / bytesTotal) * 100));
        bar.style.width = `${pct}%`;
        const template = trans.downloadProgress || '{pct}% · {read} / {total}';
        let metaText = template
            .replace('{pct}', String(pct))
            .replace('{read}', formatBytes(bytesRead))
            .replace('{total}', formatBytes(bytesTotal));
        if (etaSeconds) {
            const etaTemplate = trans.downloadProgressEta || '· ~{eta} left';
            metaText += ` ${etaTemplate.replace('{eta}', formatDownloadEta(etaSeconds))}`;
        }
        meta.textContent = metaText;
        return;
    }

    bar.classList.add('indeterminate');
    bar.style.width = '';
    meta.textContent = trans.downloadProgressIndeterminate || '';
}

function showDownloadError(message, canRetry) {
    const container = document.getElementById('downloadProgress');
    const bar = document.getElementById('downloadProgressBar');
    const label = document.getElementById('downloadProgressLabel');
    const meta = document.getElementById('downloadProgressMeta');
    const cancelBtn = document.getElementById('downloadCancelBtn');
    const retryBtn = document.getElementById('downloadRetryBtn');
    const trans = uiTranslations[currentLang] || {};
    if (!container || !bar || !label || !meta) return;

    container.hidden = false;
    bar.classList.remove('indeterminate', 'complete');
    bar.classList.add('error');
    bar.style.width = '100%';
    label.textContent = trans.toastError || 'Error';
    meta.textContent = message || '';
    if (cancelBtn) cancelBtn.hidden = true;
    if (retryBtn) retryBtn.hidden = !canRetry;
}

function hideDownloadProgress() {
    const container = document.getElementById('downloadProgress');
    const bar = document.getElementById('downloadProgressBar');
    const cancelBtn = document.getElementById('downloadCancelBtn');
    const retryBtn = document.getElementById('downloadRetryBtn');
    const showFolderBtn = document.getElementById('downloadShowFolderBtn');
    const openFileBtn = document.getElementById('downloadOpenFileBtn');
    if (container) container.hidden = true;
    if (bar) {
        bar.classList.remove('indeterminate', 'complete', 'error');
        bar.style.width = '0%';
    }
    if (cancelBtn) cancelBtn.hidden = true;
    if (retryBtn) retryBtn.hidden = true;
    if (showFolderBtn) showFolderBtn.hidden = true;
    if (openFileBtn) openFileBtn.hidden = true;
}

let downloadPollToken = 0;
let activeDownloadJobId = null;

async function pollDownloadJob(jobId, token) {
    const pollInterval = 400;
    const maxWaitMs = 30 * 60 * 1000;
    const started = Date.now();
    let lastSample = null;

    while (Date.now() - started < maxWaitMs) {
        if (token !== downloadPollToken) {
            return { cancelled: true };
        }

        const res = await fetch(`${API_BASE}/download/status?job_id=${encodeURIComponent(jobId)}`);
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(resolveApiError(err, 'toastError'));
        }
        const status = await res.json();

        let etaSeconds = null;
        if (
            status.phase === 'downloading'
            && status.bytes_total > 0
            && status.bytes_read > 0
        ) {
            const now = Date.now();
            if (lastSample && status.bytes_read > lastSample.bytes) {
                const elapsedSec = (now - lastSample.time) / 1000;
                if (elapsedSec > 0) {
                    const rate = (status.bytes_read - lastSample.bytes) / elapsedSec;
                    if (rate > 0) {
                        etaSeconds = Math.max(1, Math.round((status.bytes_total - status.bytes_read) / rate));
                    }
                }
            }
            lastSample = { bytes: status.bytes_read, time: now };
        }

        showDownloadProgress(status.phase, status.bytes_read, status.bytes_total, etaSeconds);

        if (status.done) {
            if (status.phase === 'cancelled' || status.cancelled) {
                return { cancelled: true };
            }
            if (status.error || status.error_code) {
                throw new Error(resolveApiError(status, 'toastError'));
            }
            return status;
        }

        await new Promise(resolve => setTimeout(resolve, pollInterval));
    }

    throw new Error((uiTranslations[currentLang] || {}).toastError || 'Error');
}

function cancelActiveDownload() {
    if (!activeDownloadJobId) return Promise.resolve();
    downloadPollToken += 1;
    return fetch(`${API_BASE}/download/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_id: activeDownloadJobId }),
    }).catch(() => {});
}

const downloadQueue = [];
let downloadQueueProcessing = false;
let currentQueueLabel = '';
let downloadQueueSeq = 0;
const LS_OPEN_ON_COMPLETE = 'stats_sheets_open_on_complete';
const LS_HISTORY_PANEL_OPEN = 'stats_sheets_history_panel_open';
const LS_HISTORY_FILTER = 'stats_sheets_history_filter';
const LS_DOWNLOAD_QUEUE = 'stats_sheets_download_queue';
const HISTORY_PAGE_SIZE = 10;
let historyFilterQuery = localStorage.getItem(LS_HISTORY_FILTER) || '';
let historyPage = 1;
let queueDragIndex = null;

function persistDownloadQueue() {
    try {
        if (downloadQueue.length === 0) {
            localStorage.removeItem(LS_DOWNLOAD_QUEUE);
            return;
        }
        localStorage.setItem(
            LS_DOWNLOAD_QUEUE,
            JSON.stringify(downloadQueue.map(item => ({
                request: item.request,
                dataset: item.dataset,
                format: item.format,
                label: item.label,
            })))
        );
    } catch (_) {}
}

function restoreDownloadQueue() {
    try {
        const raw = JSON.parse(localStorage.getItem(LS_DOWNLOAD_QUEUE) || '[]');
        if (!Array.isArray(raw)) return;
        downloadQueue.length = 0;
        raw.forEach(entry => {
            if (entry?.request?.url && entry?.dataset?.id) {
                downloadQueue.push({ ...entry, queueId: ++downloadQueueSeq });
            }
        });
        updateDownloadQueueUI();
    } catch (_) {}
}

function resumeDownloadQueue() {
    if (!serverConnected || downloadQueueProcessing || downloadQueue.length === 0) return;
    processDownloadQueue();
}

function getOpenOnCompletePreference() {
    const value = localStorage.getItem(LS_OPEN_ON_COMPLETE) || 'off';
    return ['off', 'folder', 'file'].includes(value) ? value : 'off';
}

function applyOpenOnComplete(status) {
    if (!serverConnected || !status?.file_path) return;
    const pref = getOpenOnCompletePreference();
    if (pref === 'folder') {
        openPathInFileManager(status.file_path);
    } else if (pref === 'file' && !status.path_is_dir) {
        openFileOnDesktop(status.file_path);
    }
}

function reorderQueue(fromIndex, toIndex) {
    if (fromIndex === toIndex) return;
    if (fromIndex < 0 || toIndex < 0 || fromIndex >= downloadQueue.length || toIndex >= downloadQueue.length) return;
    const [item] = downloadQueue.splice(fromIndex, 1);
    downloadQueue.splice(toIndex, 0, item);
    updateDownloadQueueUI();
    persistDownloadQueue();
}

function moveQueueItem(index, delta) {
    const target = index + delta;
    if (target < 0 || target >= downloadQueue.length) return;
    const [item] = downloadQueue.splice(index, 1);
    downloadQueue.splice(target, 0, item);
    updateDownloadQueueUI();
    persistDownloadQueue();
}

function removeQueueItem(index) {
    if (index < 0 || index >= downloadQueue.length) return;
    downloadQueue.splice(index, 1);
    updateDownloadQueueUI();
    persistDownloadQueue();
}

function updateDownloadQueueUI() {
    const bar = document.getElementById('downloadQueueBar');
    const textEl = document.getElementById('downloadQueueBarText');
    const clearBtn = document.getElementById('downloadQueueClearBtn');
    const listEl = document.getElementById('downloadQueueList');
    if (!bar || !textEl) return;
    const trans = uiTranslations[currentLang] || {};
    const pending = downloadQueue.length;
    if (!downloadQueueProcessing && pending === 0) {
        bar.hidden = true;
        textEl.textContent = '';
        if (clearBtn) clearBtn.hidden = true;
        if (listEl) {
            listEl.hidden = true;
            listEl.innerHTML = '';
        }
        return;
    }
    bar.hidden = false;
    const parts = [];
    if (downloadQueueProcessing && currentQueueLabel) {
        parts.push((trans.downloadQueueActive || 'Downloading: {name}').replace('{name}', currentQueueLabel));
    }
    if (pending > 0) {
        parts.push((trans.downloadQueuePending || '{count} queued').replace('{count}', String(pending)));
    }
    textEl.textContent = parts.join(' · ');
    if (clearBtn) {
        clearBtn.textContent = trans.downloadQueueClear || 'Clear queue';
        clearBtn.hidden = pending === 0;
    }
    if (listEl) {
        if (pending === 0) {
            listEl.hidden = true;
            listEl.innerHTML = '';
        } else {
            listEl.hidden = false;
            listEl.innerHTML = downloadQueue.map((item, index) => {
                const upDisabled = index === 0 ? ' disabled' : '';
                const downDisabled = index === pending - 1 ? ' disabled' : '';
                return `<li class="download-queue-item" data-queue-index="${index}">
                    <span class="download-queue-drag-handle" draggable="true" title="${escapeAttr(trans.downloadQueueDrag || 'Drag to reorder')}">⠿</span>
                    <span class="download-queue-item-label">${escapeHtml(item.label || item.request?.dataset_name || 'dataset')}</span>
                    <span class="download-queue-item-actions">
                        <button type="button" class="download-queue-move-btn" data-queue-move="-1" data-queue-index="${index}"${upDisabled} title="${escapeAttr(trans.downloadQueueMoveUp || 'Move up')}">↑</button>
                        <button type="button" class="download-queue-move-btn" data-queue-move="1" data-queue-index="${index}"${downDisabled} title="${escapeAttr(trans.downloadQueueMoveDown || 'Move down')}">↓</button>
                        <button type="button" class="download-queue-remove-btn" data-queue-index="${index}" title="${escapeAttr(trans.downloadQueueRemove || 'Remove')}">×</button>
                    </span>
                </li>`;
            }).join('');
        }
    }
}

function filterHistoryEntries(entries, query) {
    if (!query) return entries;
    const q = query.trim().toLowerCase();
    if (!q) return entries;
    return entries.filter(entry => {
        const ds = entry.dataset || {};
        const haystack = [
            ds.name,
            ds.title,
            ds.source,
            ds.package,
            ds.item,
            ds.id,
            entry.file_path,
            entry.format,
        ].filter(Boolean).join(' ').toLowerCase();
        return haystack.includes(q);
    });
}

function renderDownloadHistoryPanel() {
    const panel = document.getElementById('downloadHistoryPanel');
    const toggle = document.getElementById('downloadHistoryToggle');
    const body = document.getElementById('downloadHistoryBody');
    const listEl = document.getElementById('downloadHistoryList');
    const filterInput = document.getElementById('downloadHistoryFilter');
    if (!panel || !toggle || !body || !listEl) return;

    const trans = uiTranslations[currentLang] || {};
    if (filterInput) {
        filterInput.placeholder = trans.downloadHistoryFilterPlaceholder || 'Filter by name or path…';
        if (filterInput.value !== historyFilterQuery) {
            filterInput.value = historyFilterQuery;
        }
    }

    const pagination = document.getElementById('downloadHistoryPagination');
    const prevBtn = document.getElementById('downloadHistoryPrev');
    const nextBtn = document.getElementById('downloadHistoryNext');
    const pageLabel = document.getElementById('downloadHistoryPageLabel');

    const allEntries = DatasetStorage.loadRecentDownloads();
    const filtered = filterHistoryEntries(allEntries, historyFilterQuery);
    const totalFiltered = filtered.length;
    const totalPages = Math.max(1, Math.ceil(totalFiltered / HISTORY_PAGE_SIZE) || 1);
    if (historyPage > totalPages) historyPage = totalPages;
    if (historyPage < 1) historyPage = 1;
    const pageStart = (historyPage - 1) * HISTORY_PAGE_SIZE;
    const entries = filtered.slice(pageStart, pageStart + HISTORY_PAGE_SIZE);
    const total = allEntries.length;
    const shown = entries.length;

    if (pagination && prevBtn && nextBtn && pageLabel) {
        if (totalFiltered > HISTORY_PAGE_SIZE) {
            pagination.hidden = false;
            prevBtn.textContent = trans.downloadHistoryPrev || 'Previous';
            nextBtn.textContent = trans.downloadHistoryNext || 'Next';
            pageLabel.textContent = (trans.downloadHistoryPage || 'Page {page} of {total}')
                .replace('{page}', String(historyPage))
                .replace('{total}', String(totalPages));
            prevBtn.disabled = historyPage <= 1;
            nextBtn.disabled = historyPage >= totalPages;
        } else {
            pagination.hidden = true;
        }
    }

    if (historyFilterQuery.trim() && filtered.length !== total) {
        toggle.textContent = (trans.downloadHistoryToggleFiltered || 'Download history ({shown}/{total})')
            .replace('{shown}', String(filtered.length))
            .replace('{total}', String(total));
    } else {
        toggle.textContent = (trans.downloadHistoryToggle || 'Download history ({count})').replace('{count}', String(total));
    }

    if (total === 0) {
        listEl.innerHTML = `<li class="download-history-empty">${escapeHtml(trans.downloadHistoryEmpty || 'No downloads yet.')}</li>`;
    } else if (totalFiltered === 0 && historyFilterQuery.trim()) {
        listEl.innerHTML = `<li class="download-history-empty">${escapeHtml(trans.downloadHistoryNoMatches || 'No matching downloads.')}</li>`;
    } else {
        listEl.innerHTML = entries.map(entry => {
            const ds = entry.dataset || {};
            const name = escapeHtml(ds.name || ds.title || trans.detailUnknown || 'Unknown');
            const path = escapeHtml(entry.file_path || '');
            const timeStr = entry.at
                ? new Date(entry.at).toLocaleString(currentLang === 'ar' ? 'ar-SA' : (currentLang === 'de' ? 'de-DE' : 'en-US'))
                : '';
            const fileBtn = entry.path_is_dir
                ? ''
                : `<button type="button" class="download-history-action-btn" data-history-action="file" data-history-path="${escapeAttr(entry.file_path || '')}">${escapeHtml(trans.downloadOpenFileBtn || 'Open file')}</button>`;
            return `<li class="download-history-item">
                <div class="download-history-item-main">
                    <span class="download-history-name">${name}</span>
                    <span class="download-history-meta">${escapeHtml(timeStr)} · ${path}</span>
                </div>
                <div class="download-history-item-actions">
                    <button type="button" class="download-history-action-btn" data-history-action="folder" data-history-path="${escapeAttr(entry.file_path || '')}">${escapeHtml(trans.downloadShowFolderBtn || 'Show in folder')}</button>
                    ${fileBtn}
                </div>
            </li>`;
        }).join('');
    }

    const open = localStorage.getItem(LS_HISTORY_PANEL_OPEN) === '1';
    body.hidden = !open;
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    panel.hidden = currentTab !== 'datasets-tab' || (
        document.getElementById('datasetDetailView')?.style.display !== 'none'
    );
}

function initDownloadHistoryPanel() {
    const toggle = document.getElementById('downloadHistoryToggle');
    const body = document.getElementById('downloadHistoryBody');
    const listEl = document.getElementById('downloadHistoryList');
    const filterInput = document.getElementById('downloadHistoryFilter');
    if (!toggle || !body || !listEl) return;

    toggle.addEventListener('click', () => {
        const open = body.hidden;
        body.hidden = !open;
        toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        localStorage.setItem(LS_HISTORY_PANEL_OPEN, open ? '1' : '0');
        if (open && filterInput) filterInput.focus();
    });

    if (filterInput) {
        filterInput.value = historyFilterQuery;
        filterInput.addEventListener('input', () => {
            historyFilterQuery = filterInput.value;
            historyPage = 1;
            localStorage.setItem(LS_HISTORY_FILTER, historyFilterQuery);
            renderDownloadHistoryPanel();
        });
    }

    const prevBtn = document.getElementById('downloadHistoryPrev');
    const nextBtn = document.getElementById('downloadHistoryNext');
    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            if (historyPage > 1) {
                historyPage -= 1;
                renderDownloadHistoryPanel();
            }
        });
    }
    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            historyPage += 1;
            renderDownloadHistoryPanel();
        });
    }

    listEl.addEventListener('click', (event) => {
        const btn = event.target.closest('[data-history-action]');
        if (!btn) return;
        const path = btn.getAttribute('data-history-path');
        const action = btn.getAttribute('data-history-action');
        if (!path) return;
        if (action === 'file') openFileOnDesktop(path);
        else openPathInFileManager(path);
    });

    document.getElementById('downloadQueueList')?.addEventListener('click', (event) => {
        const moveBtn = event.target.closest('[data-queue-move]');
        if (moveBtn && !moveBtn.disabled) {
            const index = Number(moveBtn.getAttribute('data-queue-index'));
            const delta = Number(moveBtn.getAttribute('data-queue-move'));
            if (!Number.isNaN(index) && !Number.isNaN(delta)) moveQueueItem(index, delta);
            return;
        }
        const removeBtn = event.target.closest('.download-queue-remove-btn');
        if (removeBtn) {
            const index = Number(removeBtn.getAttribute('data-queue-index'));
            if (!Number.isNaN(index)) removeQueueItem(index);
        }
    });

    const queueList = document.getElementById('downloadQueueList');
    if (queueList) {
        queueList.addEventListener('dragstart', (event) => {
            const handle = event.target.closest('.download-queue-drag-handle');
            if (!handle) {
                event.preventDefault();
                return;
            }
            const item = handle.closest('.download-queue-item');
            if (!item) return;
            queueDragIndex = Number(item.getAttribute('data-queue-index'));
            if (Number.isNaN(queueDragIndex)) return;
            item.classList.add('is-dragging');
            event.dataTransfer.effectAllowed = 'move';
            event.dataTransfer.setData('text/plain', String(queueDragIndex));
        });

        queueList.addEventListener('dragend', (event) => {
            event.target.closest('.download-queue-item')?.classList.remove('is-dragging');
            queueList.querySelectorAll('.download-queue-item-drop-target').forEach(el => {
                el.classList.remove('download-queue-item-drop-target');
            });
            queueDragIndex = null;
        });

        queueList.addEventListener('dragover', (event) => {
            if (queueDragIndex === null) return;
            event.preventDefault();
            event.dataTransfer.dropEffect = 'move';
            const item = event.target.closest('.download-queue-item');
            queueList.querySelectorAll('.download-queue-item-drop-target').forEach(el => {
                el.classList.remove('download-queue-item-drop-target');
            });
            if (item) item.classList.add('download-queue-item-drop-target');
        });

        queueList.addEventListener('drop', (event) => {
            event.preventDefault();
            const item = event.target.closest('.download-queue-item');
            if (!item || queueDragIndex === null) return;
            const toIndex = Number(item.getAttribute('data-queue-index'));
            if (!Number.isNaN(toIndex)) reorderQueue(queueDragIndex, toIndex);
            queueDragIndex = null;
        });
    }

    renderDownloadHistoryPanel();
}

initDownloadHistoryPanel();

function clearPendingDownloads() {
    if (downloadQueue.length === 0) return;
    downloadQueue.length = 0;
    persistDownloadQueue();
    updateDownloadQueueUI();
    const trans = uiTranslations[currentLang] || {};
    showToast(trans.downloadQueueCleared || 'Queued downloads cleared.');
}

function openPathOnDesktop(path, action = 'folder') {
    const trans = uiTranslations[currentLang] || {};
    return fetch(`${API_BASE}/open_path`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path, action }),
    })
        .then(res => res.json().then(data => ({ ok: res.ok, data })))
        .then(({ ok, data }) => {
            if (!ok || data.error_code || data.error) {
                throw new Error(resolveApiError(data, 'downloadOpenFailed'));
            }
        })
        .catch(err => {
            showToast(err.message || trans.downloadOpenFailed || 'Could not open path.', true);
        });
}

function openPathInFileManager(path) {
    return openPathOnDesktop(path, 'folder');
}

function openFileOnDesktop(path) {
    return openPathOnDesktop(path, 'file');
}

function notifyDownloadCompleteIfHidden(datasetName, filePath) {
    if (!document.hidden) return;
    const trans = uiTranslations[currentLang] || {};
    fetch(`${API_BASE}/notify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            title: trans.downloadNotifyTitle || 'Download complete',
            body: (trans.downloadNotifyBody || '{name} → {path}')
                .replace('{name}', datasetName)
                .replace('{path}', filePath),
        }),
    }).catch(() => {});
}

async function executeDownloadItem(item) {
    const trans = uiTranslations[currentLang] || {};
    const isDetailActive = selectedDataset?.id === item.dataset.id;
    const downloadBtn = isDetailActive ? document.getElementById('startDownloadBtn') : null;
    const cancelBtn = isDetailActive ? document.getElementById('downloadCancelBtn') : null;
    const showFolderBtn = isDetailActive ? document.getElementById('downloadShowFolderBtn') : null;
    const openFileBtn = isDetailActive ? document.getElementById('downloadOpenFileBtn') : null;

    downloadPollToken += 1;
    const pollToken = downloadPollToken;
    activeDownloadJobId = null;

    if (downloadBtn) {
        downloadBtn.disabled = true;
        downloadBtn.textContent = trans.toastDownloading;
    }
    if (isDetailActive) {
        showDownloadProgress('queued', 0, null);
    }
    if (showFolderBtn) showFolderBtn.hidden = true;
    if (openFileBtn) openFileBtn.hidden = true;

    try {
        const res = await fetch(`${API_BASE}/download`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(item.request),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(resolveApiError(err, 'toastError'));
        }
        const data = await res.json();
        activeDownloadJobId = data.job_id;
        const status = await pollDownloadJob(data.job_id, pollToken);

        if (status.cancelled) {
            if (isDetailActive) {
                showDownloadError(trans.downloadCancelled || 'Download cancelled.', true);
            }
            return;
        }

        if (isDetailActive) {
            const bar = document.getElementById('downloadProgressBar');
            if (bar) {
                bar.classList.remove('indeterminate', 'error');
                bar.classList.add('complete');
                bar.style.width = '100%';
            }
            if (cancelBtn) cancelBtn.hidden = true;
            if (showFolderBtn) {
                showFolderBtn.hidden = false;
                showFolderBtn.onclick = () => openPathInFileManager(status.file_path);
            }
            if (openFileBtn) {
                if (status.path_is_dir) {
                    openFileBtn.hidden = true;
                } else {
                    openFileBtn.hidden = false;
                    openFileBtn.onclick = () => openFileOnDesktop(status.file_path);
                }
            }
        }

        if (downloadBtn) {
            downloadBtn.textContent = trans.toastSuccess;
            downloadBtn.classList.add('success');
        }

        DatasetStorage.addRecentDownload(item.dataset, status.file_path, item.format, status.path_is_dir);
        renderDownloadHistoryPanel();
        applyOpenOnComplete(status);
        notifyDownloadCompleteIfHidden(item.label, status.file_path);
        activeDownloadJobId = null;

        showDownloadCompleteModal({
            filePath: status.file_path,
            pathIsDir: !!status.path_is_dir,
            onClose: () => {
                if (isDetailActive) {
                    hideDownloadProgress();
                    if (showFolderBtn) showFolderBtn.hidden = true;
                    if (openFileBtn) openFileBtn.hidden = true;
                }
                if (downloadBtn) {
                    downloadBtn.disabled = false;
                    downloadBtn.textContent = trans.detailDownloadBtn;
                    downloadBtn.classList.remove('success');
                }
            },
        });
    } catch (err) {
        activeDownloadJobId = null;
        if (downloadBtn) {
            downloadBtn.disabled = false;
            downloadBtn.textContent = trans.detailDownloadBtn;
            downloadBtn.classList.remove('success');
        }
        if (isDetailActive) {
            showDownloadError(err.message, true);
        }
        showToast(err.message || trans.toastError, true);
    }
}

async function processDownloadQueue() {
    if (downloadQueueProcessing) return;
    downloadQueueProcessing = true;
    while (downloadQueue.length > 0) {
        const item = downloadQueue.shift();
        persistDownloadQueue();
        currentQueueLabel = item.label;
        updateDownloadQueueUI();
        await executeDownloadItem(item);
        currentQueueLabel = '';
        updateDownloadQueueUI();
    }
    downloadQueueProcessing = false;
    persistDownloadQueue();
    updateDownloadQueueUI();
}

function enqueueDownload(item) {
    downloadQueue.push({ ...item, queueId: ++downloadQueueSeq });
    persistDownloadQueue();
    updateDownloadQueueUI();
    processDownloadQueue();
}

document.getElementById('downloadQueueClearBtn')?.addEventListener('click', clearPendingDownloads);
restoreDownloadQueue();
// --- Dataset Explorer Features ---
let currentPage = 1;
let totalPages = 1;
let totalResults = 0;
const PER_PAGE = 25;

function prefetchDefaultDatasetSearch() {
    if (!serverConnected) return;
    const cacheKey = `:${activeSource}:1:${PER_PAGE}`;
    if (getSearchCacheEntry(cacheKey)) return;
    fetch(`${API_BASE}/search?q=&source=${activeSource}&page=1&per_page=${PER_PAGE}`)
        .then(res => parseSearchResponse(res))
        .then(data => {
            if (data.needs_auth) return;
            setSearchCacheEntry(cacheKey, data);
        })
        .catch(() => {});
}

// Initial Load or when source filters change
function triggerSearch(query = '', page = 1) {
    if (currentTab !== 'datasets-tab') return;
    currentPage = page;

    updateRdatasetsRefreshUI();
    updateRecentExportUI();
    renderDownloadHistoryPanel();
    const listPane = document.getElementById('datasetsList');
    if (!listPane) return;

    if (activeSource === 'favorites' || activeSource === 'recent') {
        let list = activeSource === 'favorites' ? DatasetStorage.loadFavorites() : DatasetStorage.getRecentDatasetsForList();
        list = DatasetStorage.filterByQuery(list, query);
        const paged = DatasetStorage.paginate(list, page, PER_PAGE);
        datasetsList = paged.results;
        totalPages = paged.total_pages;
        totalResults = paged.total;
        renderDatasetsList();
        return;
    }

    const cacheKey = `${query}:${activeSource}:${page}:${PER_PAGE}`;
    const cached = getSearchCacheEntry(cacheKey);
    if (cached) {
        datasetsList = cached.results || cached;
        totalPages = cached.total_pages || 1;
        totalResults = cached.total || 0;
        renderDatasetsList();
        return;
    }
    
    listPane.innerHTML = `<div style="padding: 16px; text-align: center; color: var(--text-secondary);">${(uiTranslations[currentLang] || {}).searchLoading || 'Loading...'}</div>`;
    
    fetch(`${API_BASE}/search?q=${encodeURIComponent(query)}&source=${activeSource}&page=${page}&per_page=${PER_PAGE}`)
        .then(res => parseSearchResponse(res))
        .then(data => {
            if (data.needs_auth) {
                showKaggleSetupBanner();
                datasetsList = [];
                totalPages = 1;
                totalResults = 0;
            } else {
                updateKaggleBanner();
                datasetsList = data.results || data;
                totalPages = data.total_pages || 1;
                totalResults = data.total || 0;
                if (data.kaggle_skipped) {
                    showToast(uiTranslations[currentLang].kaggleSkipped, true);
                }
                setSearchCacheEntry(cacheKey, data);
            }
            renderDatasetsList();
        })
        .catch(err => {
            const kind = classifySearchFailure(err);
            const options = kind === 'rate_limit' ? { retryAfter: err.retryAfter } : {};
            renderHttpErrorState(listPane, kind, () => triggerSearch(query, page), options);
            console.error(err);
        });
}

// Bind Filter Bar buttons
document.querySelectorAll('.filter-pill').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.filter-pill').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        activeSource = btn.dataset.source;
        currentPage = 1;
        searchInput.value = '';
        syncFilterPillTabindex();
        updateKaggleBanner();
        triggerSearch();
    });
});

function updateRecentExportUI() {
    const section = document.getElementById('recentExportSection');
    if (!section) return;
    section.style.display = activeSource === 'recent' ? 'flex' : 'none';
}

const exportRecentBtn = document.getElementById('exportRecentBtn');
if (exportRecentBtn) {
    exportRecentBtn.addEventListener('click', () => {
        const trans = uiTranslations[currentLang] || {};
        if (!DatasetStorage.exportRecentDownloadsCsv()) {
            showToast(trans.exportRecentEmpty || 'No recent downloads to export.', true);
            return;
        }
        showToast(trans.exportRecentDone || 'Recent downloads exported.');
    });
}

const kaggleRecheckBtn = document.getElementById('kaggleRecheckBtn');
if (kaggleRecheckBtn) {
    kaggleRecheckBtn.addEventListener('click', () => recheckKaggleAuth());
}
const kaggleOpenDirBtn = document.getElementById('kaggleOpenDirBtn');
if (kaggleOpenDirBtn) {
    kaggleOpenDirBtn.addEventListener('click', () => openKaggleCredentialsDir());
}

function highlightText(text, query) {
    if (!query) return text;
    const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    return text.replace(new RegExp(`(${escaped})`, 'gi'), '<mark>$1</mark>');
}

function renderDatasetsList() {
    const listPane = document.getElementById('datasetsList');
    if (!listPane) return;
    
    if (datasetsList.length === 0) {
        let variant = 'search';
        if (activeSource === 'favorites') variant = 'favorites';
        if (activeSource === 'recent') variant = 'recent';
        renderEmptyState(listPane, variant);
        return;
    }
    
    const query = searchInput.value.trim();
    
    listPane.innerHTML = '';
    datasetsList.forEach(ds => {
        const card = document.createElement('div');
        card.className = 'dataset-item-card';
        card.setAttribute('role', 'option');
        card.dataset.datasetId = ds.id;
        if (selectedDataset && selectedDataset.id === ds.id) {
            card.classList.add('active');
        }
        
        if (DatasetStorage.isFavorite(ds.id)) {
            card.classList.add('is-favorite');
        }

        let badgeClass = 'badge-r';
        let badgeLabel = 'R';
        if (ds.source === 'huggingface') {
            badgeClass = 'badge-hf';
            badgeLabel = 'HF';
        } else if (ds.source === 'kaggle') {
            badgeClass = 'badge-kaggle';
            badgeLabel = 'Kaggle';
        }
        
        let metaText = uiTranslations[currentLang].detailUnknown;
        if (ds._recentPath) {
            const timeStr = ds._recentAt ? new Date(ds._recentAt).toLocaleString() : '';
            const atLabel = (uiTranslations[currentLang].recentDownloadedAt || 'Downloaded {time}').replace('{time}', timeStr);
            metaText = `${atLabel} • ${uiTranslations[currentLang].recentFilePath}: ${escapeHtml(String(ds._recentPath))}`;
        } else if (ds.rows && ds.cols) {
            metaText = `${ds.rows.toLocaleString()} ${uiTranslations[currentLang].detailRows} • ${ds.cols} ${uiTranslations[currentLang].detailCols}`;
        } else if (ds.source === 'huggingface' || ds.source === 'kaggle') {
            metaText = `${uiTranslations[currentLang].detailDownloads}: ${ds.downloads?.toLocaleString() || 0}`;
        }

        let previewHtml = '';
        if (ds.previewable === true) {
            previewHtml = `<span class="preview-badge preview-yes">${uiTranslations[currentLang].previewYes}</span>`;
        } else if (ds.previewable === false) {
            previewHtml = `<span class="preview-badge preview-no">${uiTranslations[currentLang].previewNo}</span>`;
        }
        
        const highlightedName = highlightText(escapeHtml(ds.name), query);
        const highlightedDesc = highlightText(escapeHtml(ds.title || ds.name), query);
            
        card.innerHTML = `
            <div class="dataset-item-header">
                <span class="dataset-item-title" title="${escapeHtml(ds.name)}">${DatasetStorage.isFavorite(ds.id) ? '★ ' : ''}${highlightedName}</span>
                <span class="dataset-item-badge ${badgeClass}">${badgeLabel}</span>
            </div>
            <div class="dataset-item-desc">${highlightedDesc}</div>
            <div class="dataset-item-meta">
                <span>${metaText}</span>
                ${previewHtml}
            </div>
        `;
        
        card.addEventListener('click', () => {
            document.querySelectorAll('.dataset-item-card').forEach(c => c.classList.remove('active'));
            card.classList.add('active');
            searchView.style.display = 'none';
            detailView.style.display = 'flex';
            renderDownloadHistoryPanel();
            selectDataset(ds);
        });

        listPane.appendChild(card);
    });

    initDatasetCardTabindex();
    applyDatasetListFocusIfPending();

    // Pagination controls
    if (totalPages > 1) {
        const pagination = document.createElement('div');
        pagination.className = 'pagination-bar';

        const pageInfo = document.createElement('span');
        pageInfo.className = 'pagination-info';
        const pageLabel = (uiTranslations[currentLang].paginationLabel || 'Page {current}/{total}').replace('{current}', currentPage).replace('{total}', totalPages).replace('{count}', totalResults);
        pageInfo.textContent = pageLabel;

        const prevBtn = document.createElement('button');
        prevBtn.type = 'button';
        prevBtn.className = 'pagination-btn';
        prevBtn.textContent = '←';
        prevBtn.setAttribute('aria-label', (uiTranslations[currentLang] || {}).paginationPrev || 'Previous page');
        prevBtn.disabled = currentPage <= 1;
        prevBtn.addEventListener('click', () => {
            if (currentPage > 1) {
                requestDatasetListFocus(0);
                currentPage--;
                triggerSearch(searchInput.value.trim(), currentPage);
            }
        });

        const nextBtn = document.createElement('button');
        nextBtn.type = 'button';
        nextBtn.className = 'pagination-btn';
        nextBtn.textContent = '→';
        nextBtn.setAttribute('aria-label', (uiTranslations[currentLang] || {}).paginationNext || 'Next page');
        nextBtn.disabled = currentPage >= totalPages;
        nextBtn.addEventListener('click', () => {
            if (currentPage < totalPages) {
                requestDatasetListFocus(0);
                currentPage++;
                triggerSearch(searchInput.value.trim(), currentPage);
            }
        });

        pagination.appendChild(prevBtn);
        pagination.appendChild(pageInfo);
        pagination.appendChild(nextBtn);
        listPane.appendChild(pagination);
    }
}

function renderDetailSkeleton() {
    if (!detailContent) return;
    const trans = uiTranslations[currentLang] || {};
    const label = trans.detailLoadingPanel || trans.searchLoading || 'Loading...';
    detailContent.innerHTML = `
        <div class="detail-skeleton" aria-busy="true" aria-label="${escapeHtml(label)}">
            <div class="skeleton-block skeleton-line skeleton-line-lg"></div>
            <div class="skeleton-block skeleton-line skeleton-line-md"></div>
            <div class="skeleton-block skeleton-line skeleton-line-sm"></div>
            <div class="detail-meta-grid skeleton-meta-grid">
                <div class="skeleton-block skeleton-meta"></div>
                <div class="skeleton-block skeleton-meta"></div>
                <div class="skeleton-block skeleton-meta"></div>
                <div class="skeleton-block skeleton-meta"></div>
            </div>
            <div class="skeleton-block skeleton-panel"></div>
            <div class="skeleton-block skeleton-panel skeleton-panel-sm"></div>
            <div class="skeleton-block skeleton-code"></div>
            <div class="skeleton-block skeleton-btn"></div>
        </div>`;
}

function applyHfFileList(dataset, hfPayload, updateCodeSnippet) {
    const trans = uiTranslations[currentLang] || {};
    const hfSelect = document.getElementById('hfFileSelect');
    const sizeSpan = document.getElementById('hfDetailSize');
    if (!hfSelect) return;

    const onFailure = () => {
        hfSelect.innerHTML = '<option value="">...</option>';
        const pb = document.getElementById('previewBtn');
        if (pb) {
            pb.disabled = true;
            pb.title = trans.detailPreviewNotAvailable || '';
        }
        if (sizeSpan) {
            sizeSpan.classList.remove('loading');
            sizeSpan.textContent = trans.detailUnknown || '?';
        }
    };

    if (!hfPayload || hfPayload.error) {
        onFailure();
        return;
    }

    const data = hfPayload;
    if (data.parquet_only) {
        hfSelect.innerHTML = `<option value="">${trans.hfParquetOnly || ''}</option>`;
        const pb = document.getElementById('previewBtn');
        if (pb) {
            pb.disabled = true;
            pb.title = trans.detailPreviewNotAvailable || '';
        }
        if (sizeSpan) {
            sizeSpan.classList.remove('loading');
            sizeSpan.textContent = trans.detailUnknown || '?';
        }
        return;
    }

    const files = data.files || data;
    if (!Array.isArray(files) || files.length === 0) {
        onFailure();
        return;
    }

    hfSelect.innerHTML = '';
    files.forEach(f => {
        const opt = document.createElement('option');
        opt.value = f.path;
        opt.textContent = f.path;
        hfSelect.appendChild(opt);
    });

    let activeSize = 0;
    const firstCsv = files.find(f => f.path.toLowerCase().endsWith('.csv'));
    if (firstCsv) {
        hfSelect.value = firstCsv.path;
        activeSize = firstCsv.size;
    } else {
        hfSelect.value = files[0].path;
        activeSize = files[0].size;
    }
    hfSelect.dataset.selectedFile = hfSelect.value;
    if (sizeSpan) {
        sizeSpan.classList.remove('loading');
        sizeSpan.textContent = activeSize ? formatBytes(activeSize) : (trans.detailUnknown || '?');
    }
    const isParquet = hfSelect.value.toLowerCase().endsWith('.parquet');
    const pb = document.getElementById('previewBtn');
    if (pb) {
        pb.disabled = isParquet && !parquetAvailable;
        pb.title = (isParquet && !parquetAvailable) ? (trans.detailPreviewNotAvailable || '') : '';
    }
    if (typeof updateCodeSnippet === 'function') updateCodeSnippet();

    hfSelect.addEventListener('change', () => {
        hfSelect.dataset.selectedFile = hfSelect.value;
        const selectedFileObj = files.find(f => f.path === hfSelect.value);
        if (sizeSpan) {
            sizeSpan.textContent = (selectedFileObj && selectedFileObj.size)
                ? formatBytes(selectedFileObj.size)
                : (trans.detailUnknown || '?');
        }
        const isParquetFile = hfSelect.value.toLowerCase().endsWith('.parquet');
        const previewBtn = document.getElementById('previewBtn');
        if (previewBtn) {
            previewBtn.disabled = isParquetFile && !parquetAvailable;
            previewBtn.title = (isParquetFile && !parquetAvailable)
                ? (trans.detailPreviewNotAvailable || '')
                : '';
        }
        if (typeof updateCodeSnippet === 'function') updateCodeSnippet();
    });
}

function renderPreviewSkeleton(container) {
    if (!container) return;
    const trans = uiTranslations[currentLang] || {};
    const label = trans.loadingPreview || 'Loading...';
    const colCount = 5;
    const rowCount = 6;
    const headerCells = Array.from({ length: colCount }, () =>
        '<div class="preview-skeleton-cell preview-skeleton-head"></div>'
    ).join('');
    const bodyRows = Array.from({ length: rowCount }, () =>
        `<div class="preview-skeleton-row">${Array.from({ length: colCount }, () =>
            '<div class="preview-skeleton-cell"></div>'
        ).join('')}</div>`
    ).join('');
    container.innerHTML = `
        <div class="preview-skeleton" aria-busy="true" aria-label="${escapeHtml(label)}">
            <div class="preview-skeleton-row preview-skeleton-header">${headerCells}</div>
            ${bodyRows}
        </div>`;
}

function renderPreviewTable(container, data) {
    if (!container || !data.columns?.length) return false;
    let html = '<table class="preview-table"><thead><tr>';
    data.columns.forEach(col => { html += `<th>${escapeHtml(col)}</th>`; });
    html += '</tr></thead><tbody>';
    data.rows.forEach(row => {
        html += '<tr>';
        data.columns.forEach(col => {
            let val = row[col] !== undefined ? row[col] : '';
            if (typeof val === 'object' && val !== null) {
                val = JSON.stringify(val);
            }
            html += `<td>${escapeHtml(String(val))}</td>`;
        });
        html += '</tr>';
    });
    html += '</tbody></table>';
    container.innerHTML = html;
    return true;
}

// Select a Dataset & Load Details Panel
function selectDataset(dataset) {
    selectedDataset = dataset;
    if (!detailContent) return;
    renderDetailSkeleton();
    const loadId = dataset.id;

    if (dataset.source === 'huggingface') {
        fetch(`${API_BASE}/hf_files?dataset_id=${encodeURIComponent(dataset.item)}`)
            .then(res => res.json())
            .then(hfData => {
                if (selectedDataset?.id !== loadId) return;
                renderDatasetDetailContent(dataset, hfData);
            })
            .catch(err => {
                if (selectedDataset?.id !== loadId) return;
                console.error(err);
                renderDatasetDetailContent(dataset, { error: true });
            });
        return;
    }

    requestAnimationFrame(() => {
        if (selectedDataset?.id !== loadId) return;
        renderDatasetDetailContent(dataset, null);
    });
}

function renderDatasetDetailContent(dataset, hfPayload) {
    if (!detailContent) return;

    // Set default target directory (per source, then global fallback)
    const defaultDir = DatasetStorage.getTargetDirForSource(dataset.source, xdgDownloadsDir);
    let selectedFormat = DatasetStorage.getFormatForSource(dataset.source);
    if (!rAvailable && (selectedFormat === 'rdata' || selectedFormat === 'rds')) {
        selectedFormat = 'csv';
    }
    
    // Show dataset details using original name/title (no dynamic translation)
    const trans = uiTranslations[currentLang];
    const translatedName = dataset.name;
    const translatedTitle = dataset.title || dataset.name;
    
    let sourceMetaHtml = '';
    let configHtml = '';
    
    if (dataset.source === 'kaggle') {
        const kaggleSizeBytes = parseKaggleSizeBytes(dataset.size);
        const kaggleSizeLabel = kaggleSizeBytes != null
            ? formatBytes(kaggleSizeBytes)
            : (dataset.size || trans.detailUnknown);
        sourceMetaHtml = `
            <div class="detail-header">
                <a href="${dataset.url}" target="_blank" class="detail-source-link">${trans.detailKaggleLink}</a>
                <div class="detail-title">${translatedName}</div>
                <div class="detail-desc">${translatedTitle}</div>
            </div>
                <div class="detail-meta-grid">
                    <div class="meta-item">
                        <span class="meta-label">${trans.detailAuthor}</span>
                        <span class="meta-value" title="${escapeHtml(dataset.package)}">${escapeHtml(dataset.package)}</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">${trans.detailLikes}</span>
                        <span class="meta-value">${dataset.likes?.toLocaleString() || 0}</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">${trans.detailDownloads}</span>
                        <span class="meta-value">${dataset.downloads?.toLocaleString() || 0}</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">${trans.detailSize}</span>
                        <span class="meta-value">${kaggleSizeLabel}</span>
                    </div>
                </div>
            `;
            configHtml = `
                <p style="font-size: 12px; color: var(--text-secondary);">${trans.detailKaggleNote}</p>
            `;
        } else if (dataset.source === 'huggingface') {
            sourceMetaHtml = `
                <div class="detail-header">
                    <a href="${dataset.url}" target="_blank" class="detail-source-link">${trans.detailHfLink}</a>
                    <div class="detail-title">${translatedName}</div>
                    <div class="detail-desc">${translatedTitle}</div>
                </div>
                <div class="detail-meta-grid">
                    <div class="meta-item">
                        <span class="meta-label">${trans.detailAuthor}</span>
                        <span class="meta-value" title="${escapeHtml(dataset.package)}">${escapeHtml(dataset.package)}</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">${trans.detailLikes}</span>
                        <span class="meta-value">${dataset.likes?.toLocaleString() || 0}</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">${trans.detailDownloads}</span>
                        <span class="meta-value">${dataset.downloads?.toLocaleString() || 0}</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">${trans.detailSize}</span>
                        <span class="meta-value loading" id="hfDetailSize">...</span>
                    </div>
                </div>
            `;
            configHtml = `
                <div class="config-row">
                    <label for="hfFileSelect">${trans.detailHfFileLabel}</label>
                    <div class="select-wrapper">
                        <select id="hfFileSelect">
                            <option value="">...</option>
                        </select>
                    </div>
                </div>
            `;
        } else {
            // Classic Rdataset
            sourceMetaHtml = `
                <div class="detail-header">
                    ${dataset.doc_url ? `<a href="${dataset.doc_url}" target="_blank" class="detail-source-link">${trans.detailDocLink}</a>` : ''}
                    <div class="detail-title">${translatedName}</div>
                    <div class="detail-desc">${translatedTitle}</div>
                </div>
                <div class="detail-meta-grid">
                    <div class="meta-item">
                        <span class="meta-label">R-Paket</span>
                        <span class="meta-value">${escapeHtml(dataset.package)}</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">${trans.detailRows}</span>
                        <span class="meta-value">${dataset.rows?.toLocaleString() || trans.detailUnknown}</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">${trans.detailCols}</span>
                        <span class="meta-value">${dataset.cols?.toLocaleString() || trans.detailUnknown}</span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">${trans.detailSize}</span>
                        <span class="meta-value loading" id="rDetailSize">...</span>
                    </div>
                </div>
            `;
        }
        
        detailContent.innerHTML = `
            ${sourceMetaHtml}
            
            <div class="detail-config-section">
                ${configHtml}
                
                <div class="config-row">
                    <label for="detailDirInput">${trans.detailTargetFolder}</label>
                    <div class="path-input-container">
                        <input type="text" id="detailDirInput" value="${escapeAttr(defaultDir)}" placeholder="${escapeAttr(xdgDownloadsDir)}">
                        <button type="button" class="path-btn" id="projectPathBtn" title="${escapeAttr(trans.detailProjectBtnTitle || trans.detailProjectBtn)}">${trans.detailProjectBtn}</button>
                    </div>
                    <p class="config-hint">${trans.detailTargetFolderHint}</p>
                </div>
                
                <div class="config-row">
                    <label>${trans.detailFormatLabel}</label>
                    <div class="format-selector">
                        <div class="format-pill${selectedFormat === 'csv' ? ' active' : ''}" data-format="csv">CSV</div>
                        <div class="format-pill${selectedFormat === 'rdata' ? ' active' : ''}${rAvailable ? '' : ' disabled'}" data-format="rdata">RData</div>
                        <div class="format-pill${selectedFormat === 'rds' ? ' active' : ''}${rAvailable ? '' : ' disabled'}" data-format="rds">RDS</div>
                        <div class="format-pill${selectedFormat === 'json' ? ' active' : ''}" data-format="json">JSON</div>
                    </div>
                    <p class="config-hint">${trans.detailFormatHint}</p>
                </div>
                
                <div class="config-row">
                    <label>${trans.detailCodeLabel}</label>
                    <div class="code-integration-panel">
                        <div class="code-tabs">
                            <button class="code-tab ${activeCodeTab === 'r' ? 'active' : ''}" data-lang="r">R</button>
                            <button class="code-tab ${activeCodeTab === 'py' ? 'active' : ''}" data-lang="py">Python (pandas)</button>
                        </div>
                        <div class="code-body-wrapper">
                            <button class="code-copy-btn" id="snippetCopyBtn">${trans.detailCopyBtn}</button>
                            <pre><code id="integrationCodeBlock">${trans.detailLoadingCode}</code></pre>
                        </div>
                    </div>
                </div>
                
                <button class="detail-preview-btn" id="previewBtn">${trans.detailPreviewBtn}</button>
                <div id="previewContainer" class="preview-container" style="display:none;">
                    <div class="preview-header">
                        <span>${trans.detailPreviewTitle}</span>
                        <button class="preview-close-btn" id="previewCloseBtn">${trans.detailPreviewClose}</button>
                    </div>
                    <div class="preview-table-wrapper" id="previewTableWrapper"></div>
                </div>
                
                <div class="config-row">
                    <label for="openOnCompleteSelect">${trans.downloadOpenOnCompleteLabel}</label>
                    <select id="openOnCompleteSelect" class="download-pref-select">
                        <option value="off">${trans.downloadOpenOnCompleteOff}</option>
                        <option value="folder">${trans.downloadOpenOnCompleteFolder}</option>
                        <option value="file">${trans.downloadOpenOnCompleteFile}</option>
                    </select>
                </div>
                
                <button class="detail-download-btn" id="startDownloadBtn">${trans.detailDownloadBtn}</button>
                <div class="download-progress" id="downloadProgress" hidden>
                    <div class="download-progress-label" id="downloadProgressLabel"></div>
                    <div class="download-progress-track">
                        <div class="download-progress-bar" id="downloadProgressBar"></div>
                    </div>
                    <div class="download-progress-meta" id="downloadProgressMeta"></div>
                    <div class="download-progress-actions">
                        <button type="button" class="download-open-file-btn" id="downloadOpenFileBtn" hidden>${trans.downloadOpenFileBtn}</button>
                        <button type="button" class="download-show-folder-btn" id="downloadShowFolderBtn" hidden>${trans.downloadShowFolderBtn}</button>
                        <button type="button" class="download-cancel-btn" id="downloadCancelBtn" hidden>${trans.downloadCancelBtn}</button>
                        <button type="button" class="download-retry-btn" id="downloadRetryBtn" hidden>${trans.downloadRetryBtn}</button>
                    </div>
                </div>
            </div>
        `;
        
        setupFavoriteButton(dataset);

        // --- Hook up listeners in Details Panel ---
        const dirInput = document.getElementById('detailDirInput');
        const projectBtn = document.getElementById('projectPathBtn');
        const downloadBtn = document.getElementById('startDownloadBtn');
        const openOnCompleteSelect = document.getElementById('openOnCompleteSelect');
        
        if (openOnCompleteSelect) {
            openOnCompleteSelect.value = getOpenOnCompletePreference();
            openOnCompleteSelect.addEventListener('change', () => {
                localStorage.setItem(LS_OPEN_ON_COMPLETE, openOnCompleteSelect.value);
            });
        }
        
        // Save target path on change
        dirInput.addEventListener('input', () => {
            const value = dirInput.value.trim();
            localStorage.setItem('last_target_dir', value);
            DatasetStorage.saveTargetDirForSource(dataset.source, value);
            updateCodeSnippet();
        });
        
        // Fast path: use Documents as target and open in file manager
        if (projectBtn) {
            projectBtn.addEventListener('click', () => {
                const folder = xdgDocumentsDir || '~/Documents';
                dirInput.value = folder;
                localStorage.setItem('last_target_dir', folder);
                DatasetStorage.saveTargetDirForSource(dataset.source, folder);
                updateCodeSnippet();
                showToast(
                    (trans.detailProjectSet || 'Target folder: {path}').replace('{path}', folder)
                );
                if (serverConnected) {
                    openPathInFileManager(folder);
                }
            });
        }
        
        // Format selections
        const formats = detailContent.querySelectorAll('.format-pill');
        formats.forEach(f => {
            f.addEventListener('click', () => {
                if (f.classList.contains('disabled')) {
                    showToast(trans.toastRNotAvailable, true);
                    return;
                }
                formats.forEach(p => p.classList.remove('active'));
                f.classList.add('active');
                selectedFormat = f.dataset.format;
                DatasetStorage.saveFormatForSource(dataset.source, selectedFormat);
                updateCodeSnippet();
            });
        });
        
        // Language tabs
        const codeTabs = detailContent.querySelectorAll('.code-tab');
        codeTabs.forEach(ct => {
            ct.addEventListener('click', () => {
                codeTabs.forEach(t => t.classList.remove('active'));
                ct.classList.add('active');
                activeCodeTab = ct.dataset.lang;
                updateCodeSnippet();
            });
        });
        
        // Code snippet copy button
        const copyBtn = document.getElementById('snippetCopyBtn');
        copyBtn.addEventListener('click', () => {
            const codeElement = document.getElementById('integrationCodeBlock');
            copyToClipboard(codeElement.textContent).then(() => {
                showToast(trans.toastCopyCode);
            });
        });
        
        // Dynamic fetch for R dataset size
        if (dataset.source === 'rdatasets') {
            const rSizeSpan = document.getElementById('rDetailSize');
            if (rSizeSpan && dataset.url) {
                fetch(`${API_BASE}/url_size?url=${encodeURIComponent(dataset.url)}`)
                    .then(res => parseJsonResponse(res))
                    .then(resData => {
                        rSizeSpan.classList.remove('loading');
                        if (resData.size) {
                            rSizeSpan.textContent = formatBytes(resData.size);
                        } else {
                            rSizeSpan.textContent = trans.detailUnknown;
                        }
                    })
                    .catch(err => {
                        rSizeSpan.classList.remove('loading');
                        rSizeSpan.textContent = err.message || trans.detailUnknown;
                    });
            }
        }
        
        // Dynamic integration snippet updater
        function updateCodeSnippet() {
            const codeElement = document.getElementById('integrationCodeBlock');
            if (!codeElement) return;
            
            let dsName = dataset.name;
            if (dataset.source === 'huggingface') {
                const hfFile = document.getElementById('hfFileSelect')?.value || '';
                if (hfFile) {
                    const parts = hfFile.split('/');
                    const filename = parts[parts.length - 1];
                    dsName = filename.replace(/\.[^/.]+$/, "");
                }
            }
            
            const formatExt = selectedFormat === 'rdata' ? '.RData' : `.${selectedFormat}`;
            const finalFilename = `${dsName}${formatExt}`;
            
            let code = '';
            if (activeCodeTab === 'r') {
                if (selectedFormat === 'csv') {
                    code = `df <- read.csv("${finalFilename}")\nhead(df)`;
                } else if (selectedFormat === 'rdata') {
                    code = `load("${finalFilename}") # ${trans.rCodeComment}`;
                } else if (selectedFormat === 'rds') {
                    code = `df <- readRDS("${finalFilename}")\nhead(df)`;
                } else if (selectedFormat === 'json') {
                    code = `library(jsonlite)\ndf <- fromJSON("${finalFilename}")\nhead(df)`;
                }
            } else {
                // Python Tab
                if (selectedFormat === 'csv') {
                    code = `import pandas as pd\ndf = pd.read_csv("${finalFilename}")\nprint(df.head())`;
                } else if (selectedFormat === 'rdata') {
                    code = `# ${trans.pyRdataComment}\n# ${trans.pyPreferredFormat}`;
                } else if (selectedFormat === 'rds') {
                    code = `# ${trans.pyRdataComment}\n# ${trans.pyPreferredFormat}`;
                } else if (selectedFormat === 'json') {
                    code = `import pandas as pd\ndf = pd.read_json("${finalFilename}")\nprint(df.head())`;
                }
            }
            codeElement.textContent = code;
        }
        
        // Initial snippet run
        updateCodeSnippet();

        if (dataset.source === 'huggingface') {
            applyHfFileList(dataset, hfPayload, updateCodeSnippet);
        }
        
        // --- Preview button ---
        const previewBtn = document.getElementById('previewBtn');
        const previewContainer = document.getElementById('previewContainer');
        const previewCloseBtn = document.getElementById('previewCloseBtn');
        const previewTableWrapper = document.getElementById('previewTableWrapper');
        let previewLoadId = 0;
        
        function getPreviewUrl() {
            if (dataset.source === 'kaggle') {
                if (!isKagglePreviewAllowed(dataset)) return null;
                return `kaggle:${dataset.item}`;
            }
            if (dataset.source === 'huggingface') {
                const hfFile = document.getElementById('hfFileSelect')?.value || '';
                if (!hfFile) return null;
                return `https://huggingface.co/datasets/${dataset.item}/resolve/main/${hfFile}`;
            }
            return dataset.url;
        }
        
        previewBtn.addEventListener('click', () => {
            const trans = uiTranslations[currentLang];
            if (previewBtn.disabled) return;
            if (dataset.source === 'kaggle' && !isKagglePreviewAllowed(dataset)) {
                showToast(trans.kagglePreviewTooLarge || trans.detailPreviewNotAvailable, true);
                return;
            }
            const previewUrl = getPreviewUrl();
            if (!previewUrl) {
                showToast(trans.detailPreviewNotAvailable, true);
                return;
            }
            previewContainer.style.display = 'block';
            const loadId = ++previewLoadId;
            renderPreviewSkeleton(previewTableWrapper);
            let previewUrlFull = `${API_BASE}/preview?url=${encodeURIComponent(previewUrl)}`;
            if (dataset.source === 'kaggle' && dataset.size) {
                previewUrlFull += `&size=${encodeURIComponent(String(dataset.size))}`;
            }
            const controller = new AbortController();
            const previewTimeoutMs = 45000;
            const timeoutId = setTimeout(() => controller.abort(), previewTimeoutMs);
            fetch(previewUrlFull, { signal: controller.signal })
                .then(async res => {
                    if (loadId !== previewLoadId) return;
                    let data;
                    try {
                        data = await parseJsonResponse(res);
                    } catch (err) {
                        previewTableWrapper.innerHTML = `<div class="preview-error">${escapeHtml(err.message || trans.toastError)}</div>`;
                        return;
                    }
                    if (data.error || data.error_code) {
                        const message = resolveApiError(data, 'toastError');
                        previewTableWrapper.innerHTML = `<div class="preview-error">${escapeHtml(message)}</div>`;
                        return;
                    }
                    if (!renderPreviewTable(previewTableWrapper, data)) {
                        previewTableWrapper.innerHTML = `<div class="preview-error preview-error-muted">${escapeHtml(trans.detailUnknown)}</div>`;
                    }
                })
                .catch(err => {
                    if (loadId !== previewLoadId) return;
                    const message = err.name === 'AbortError'
                        ? (trans.kagglePreviewTimeout || trans.toastError)
                        : (err.message || trans.toastError);
                    previewTableWrapper.innerHTML = `<div class="preview-error">${escapeHtml(message)}</div>`;
                })
                .finally(() => clearTimeout(timeoutId));
        });
        
        if (dataset.source === 'kaggle' && !isKagglePreviewAllowed(dataset)) {
            previewBtn.disabled = true;
            previewBtn.title = trans.kagglePreviewTooLarge || trans.detailPreviewNotAvailable || '';
        }
        
        previewCloseBtn.addEventListener('click', () => {
            previewLoadId += 1;
            previewContainer.style.display = 'none';
        });
        
        // --- Start Download button click ---
        const cancelBtn = document.getElementById('downloadCancelBtn');
        const retryBtn = document.getElementById('downloadRetryBtn');

        function buildDownloadRequest() {
            let downloadUrl = '';
            let targetName = dataset.name;

            if (dataset.source === 'kaggle') {
                downloadUrl = `kaggle:${dataset.item}`;
                targetName = dataset.name;
            } else if (dataset.source === 'huggingface') {
                const hfFile = document.getElementById('hfFileSelect')?.value || '';
                if (!hfFile) {
                    return { error: trans.hfFileNotFound };
                }
                downloadUrl = `https://huggingface.co/datasets/${dataset.item}/resolve/main/${hfFile}`;
                const parts = hfFile.split('/');
                const filename = parts[parts.length - 1];
                targetName = filename.replace(/\.[^/.]+$/, '');
            } else {
                downloadUrl = dataset.url;
                targetName = dataset.name.toLowerCase();
            }

            return {
                url: downloadUrl,
                dataset_name: targetName,
                format: selectedFormat,
                target_dir: dirInput.value.trim(),
            };
        }

        function runDownload() {
            const request = buildDownloadRequest();
            if (request.error) {
                showToast(request.error, true);
                return;
            }

            const item = {
                request,
                dataset,
                format: selectedFormat,
                label: request.dataset_name,
            };

            if (downloadQueueProcessing || downloadQueue.length > 0) {
                enqueueDownload(item);
                showToast(trans.downloadQueued || 'Added to download queue.');
                return;
            }

            enqueueDownload(item);
        }

        downloadBtn.addEventListener('click', runDownload);

        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => {
                cancelBtn.disabled = true;
                cancelActiveDownload().finally(() => {
                    cancelBtn.disabled = false;
                });
            });
        }

        if (retryBtn) {
            retryBtn.addEventListener('click', () => {
                hideDownloadProgress();
                runDownload();
            });
        }
}
