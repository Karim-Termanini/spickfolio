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
// --- Dataset Explorer Features ---
let currentPage = 1;
let totalPages = 1;
let totalResults = 0;
const PER_PAGE = 25;

// Initial Load or when source filters change
function triggerSearch(query = '', page = 1) {
    if (currentTab !== 'datasets-tab') return;
    currentPage = page;

    updateRdatasetsRefreshUI();
    updateRecentExportUI();
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
    
    listPane.innerHTML = `<div style="padding: 16px; text-align: center; color: var(--text-secondary);">${uiTranslations[currentLang].searchLoading}</div>`;
    
    fetch(`${API_BASE}/search?q=${encodeURIComponent(query)}&source=${activeSource}&page=${page}&per_page=${PER_PAGE}`)
        .then(res => res.json())
        .then(data => {
            if (data.needs_auth) {
                if(kaggleBanner) kaggleBanner.style.display = 'block';
                datasetsList = [];
                totalPages = 1;
                totalResults = 0;
            } else {
                if(kaggleBanner) kaggleBanner.style.display = 'none';
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
            listPane.innerHTML = `<div style="padding: 16px; text-align: center; color: var(--accent-red);">${uiTranslations[currentLang].connectionError}</div>`;
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
        searchInput.value = ''; // Clear search when changing source
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

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
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
        let emptyMsg = uiTranslations[currentLang].noDatasets;
        if (activeSource === 'favorites') emptyMsg = uiTranslations[currentLang].noFavorites;
        if (activeSource === 'recent') emptyMsg = uiTranslations[currentLang].noRecents;
        listPane.innerHTML = `<div style="padding: 16px; text-align: center; color: var(--text-secondary);">${emptyMsg}</div>`;
        return;
    }
    
    const query = searchInput.value.trim();
    
    listPane.innerHTML = '';
    datasetsList.forEach(ds => {
        const card = document.createElement('div');
        card.className = 'dataset-item-card';
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
            selectDataset(ds);
        });
        
        card.setAttribute('tabindex', '0');
        card.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                card.click();
                return;
            }
            if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                e.preventDefault();
                const cards = [...listPane.querySelectorAll('.dataset-item-card')];
                const idx = cards.indexOf(card);
                const next = e.key === 'ArrowDown' ? idx + 1 : idx - 1;
                if (next >= 0 && next < cards.length) {
                    cards[next].focus();
                }
            }
        });
        
        listPane.appendChild(card);
    });

    // Pagination controls
    if (totalPages > 1) {
        const pagination = document.createElement('div');
        pagination.className = 'pagination-bar';

        const pageInfo = document.createElement('span');
        pageInfo.className = 'pagination-info';
        const pageLabel = (uiTranslations[currentLang].paginationLabel || 'Page {current}/{total}').replace('{current}', currentPage).replace('{total}', totalPages).replace('{count}', totalResults);
        pageInfo.textContent = pageLabel;

        const prevBtn = document.createElement('button');
        prevBtn.className = 'pagination-btn';
        prevBtn.textContent = '←';
        prevBtn.disabled = currentPage <= 1;
        prevBtn.addEventListener('click', () => {
            if (currentPage > 1) {
                currentPage--;
                triggerSearch(searchInput.value.trim(), currentPage);
            }
        });

        const nextBtn = document.createElement('button');
        nextBtn.className = 'pagination-btn';
        nextBtn.textContent = '→';
        nextBtn.disabled = currentPage >= totalPages;
        nextBtn.addEventListener('click', () => {
            if (currentPage < totalPages) {
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

// Select a Dataset & Load Details Panel
function selectDataset(dataset) {
    selectedDataset = dataset;
    if (!detailContent) return;
    
    // Set default target directory
    const defaultDir = localStorage.getItem('last_target_dir') || xdgDownloadsDir;
    
    // Show dataset details using original name/title (no dynamic translation)
    const trans = uiTranslations[currentLang];
    const translatedName = dataset.name;
    const translatedTitle = dataset.title || dataset.name;
    
    let sourceMetaHtml = '';
    let configHtml = '';
    
    if (dataset.source === 'kaggle') {
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
                        <span class="meta-value">${dataset.size || trans.detailUnknown}</span>
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
                        <input type="text" id="detailDirInput" value="${defaultDir}" placeholder="${xdgDownloadsDir}">
                        <button class="path-btn" id="projectPathBtn" title="Nutze das aktuelle Dokumentenverzeichnis">${trans.detailProjectBtn}</button>
                    </div>
                </div>
                
                <div class="config-row">
                    <label>${trans.detailFormatLabel}</label>
                    <div class="format-selector">
                        <div class="format-pill active" data-format="csv">CSV</div>
                        <div class="format-pill ${rAvailable ? '' : 'disabled'}" data-format="rdata">RData</div>
                        <div class="format-pill ${rAvailable ? '' : 'disabled'}" data-format="rds">RDS</div>
                        <div class="format-pill" data-format="json">JSON</div>
                    </div>
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
                    <div class="preview-table-wrapper" id="previewTableWrapper">
                        <div style="text-align:center;padding:24px;color:var(--text-secondary);">${trans.loadingPreview}</div>
                    </div>
                </div>
                
                <button class="detail-download-btn" id="startDownloadBtn">${trans.detailDownloadBtn}</button>
            </div>
        `;
        
        setupFavoriteButton(dataset);

        // --- Hook up listeners in Details Panel ---
        const dirInput = document.getElementById('detailDirInput');
        const projectBtn = document.getElementById('projectPathBtn');
        const downloadBtn = document.getElementById('startDownloadBtn');
        
        // Save target path on change
        dirInput.addEventListener('input', () => {
            localStorage.setItem('last_target_dir', dirInput.value.trim());
            updateCodeSnippet();
        });
        
        // Fast path toggle
        projectBtn.addEventListener('click', () => {
            dirInput.value = xdgDocumentsDir;
            localStorage.setItem('last_target_dir', dirInput.value);
            updateCodeSnippet();
        });
        
        // Format selections
        let selectedFormat = 'csv';
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
                    .then(res => res.json())
                    .then(resData => {
                        rSizeSpan.classList.remove('loading');
                        if (resData.size) {
                            rSizeSpan.textContent = formatBytes(resData.size);
                        } else {
                            rSizeSpan.textContent = trans.detailUnknown;
                        }
                    })
                    .catch(() => {
                        rSizeSpan.classList.remove('loading');
                        rSizeSpan.textContent = trans.detailUnknown;
                    });
            }
        }
        
        // Hugging Face file tree populating
        let selectedHfFile = '';
        if (dataset.source === 'huggingface') {
            const hfSelect = document.getElementById('hfFileSelect');
            fetch(`${API_BASE}/hf_files?dataset_id=${encodeURIComponent(dataset.item)}`)
                .then(res => res.json())
                .then(data => {
                    if (data.error) throw new Error(data.error);
                    if (data.parquet_only) {
                        hfSelect.innerHTML = `<option value="">${trans.hfParquetOnly}</option>`;
                        const pb = document.getElementById('previewBtn');
                        if (pb) { pb.disabled = true; pb.title = trans.detailPreviewNotAvailable; }
                        return;
                    }
                    const files = data.files || data;
                    if (!Array.isArray(files) || files.length === 0) {
                        hfSelect.innerHTML = '<option value="">...</option>';
                        const pb = document.getElementById('previewBtn');
                        if (pb) { pb.disabled = true; pb.title = trans.detailPreviewNotAvailable; }
                        return;
                    }

                    hfSelect.innerHTML = '';
                    files.forEach(f => {
                        const opt = document.createElement('option');
                        opt.value = f.path;
                        opt.textContent = f.path;
                        hfSelect.appendChild(opt);
                    });

                    // Auto-select first csv or first file
                    let activeSize = 0;
                    const firstCsv = files.find(f => f.path.toLowerCase().endsWith('.csv'));
                    if (firstCsv) {
                        hfSelect.value = firstCsv.path;
                        activeSize = firstCsv.size;
                    } else {
                        hfSelect.value = files[0].path;
                        activeSize = files[0].size;
                    }
                    selectedHfFile = hfSelect.value;
                    const sizeSpan = document.getElementById('hfDetailSize');
                    if (sizeSpan) {
                        sizeSpan.classList.remove('loading');
                        sizeSpan.textContent = activeSize ? formatBytes(activeSize) : trans.detailUnknown;
                    }
                    const isParquet = selectedHfFile.toLowerCase().endsWith('.parquet');
                    const pb = document.getElementById('previewBtn');
                    if (pb) {
                        pb.disabled = isParquet && !parquetAvailable;
                        pb.title = (isParquet && !parquetAvailable) ? trans.detailPreviewNotAvailable : '';
                    }
                    updateCodeSnippet();

                    // Update size on change
                    hfSelect.addEventListener('change', () => {
                        selectedHfFile = hfSelect.value;
                        const selectedFileObj = files.find(f => f.path === selectedHfFile);
                        if (sizeSpan) {
                            sizeSpan.textContent = (selectedFileObj && selectedFileObj.size) ? formatBytes(selectedFileObj.size) : trans.detailUnknown;
                        }
                        const isParquet = selectedHfFile.toLowerCase().endsWith('.parquet');
                        const pb = document.getElementById('previewBtn');
                        if (pb) {
                            pb.disabled = isParquet && !parquetAvailable;
                            pb.title = (isParquet && !parquetAvailable) ? trans.detailPreviewNotAvailable : '';
                        }
                        updateCodeSnippet();
                    });
                })
                .catch(err => {
                    hfSelect.innerHTML = '<option value="">...</option>';
                    const pb = document.getElementById('previewBtn');
                    if (pb) { pb.disabled = true; pb.title = trans.detailPreviewNotAvailable; }
                    if (sizeSpan) {
                        sizeSpan.classList.remove('loading');
                        sizeSpan.textContent = trans.detailUnknown;
                    }
                    console.error(err);
                });
        }
        
        // Dynamic integration snippet updater
        function updateCodeSnippet() {
            const codeElement = document.getElementById('integrationCodeBlock');
            if (!codeElement) return;
            
            let dsName = dataset.name;
            if (dataset.source === 'huggingface') {
                if (selectedHfFile) {
                    const parts = selectedHfFile.split('/');
                    const filename = parts[parts.length - 1];
                    dsName = filename.replace(/\.[^/.]+$/, ""); // Strip extension
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
        
        // --- Preview button ---
        const previewBtn = document.getElementById('previewBtn');
        const previewContainer = document.getElementById('previewContainer');
        const previewCloseBtn = document.getElementById('previewCloseBtn');
        const previewTableWrapper = document.getElementById('previewTableWrapper');
        
        function getPreviewUrl() {
            if (dataset.source === 'kaggle') return `kaggle:${dataset.item}`;
            if (dataset.source === 'huggingface') {
                const hfFile = selectedHfFile || (document.getElementById('hfFileSelect')?.value || '');
                if (!hfFile) return null;
                return `https://huggingface.co/datasets/${dataset.item}/resolve/main/${hfFile}`;
            }
            return dataset.url;
        }
        
        previewBtn.addEventListener('click', () => {
            const trans = uiTranslations[currentLang];
            if (previewBtn.disabled) return;
            const previewUrl = getPreviewUrl();
            if (!previewUrl) {
                showToast(trans.detailPreviewNotAvailable, true);
                return;
            }
            previewContainer.style.display = 'block';
            previewTableWrapper.innerHTML = `<div style="text-align:center;padding:24px;color:var(--text-secondary);">${trans.detailPreviewTitle}...</div>`;
            fetch(`${API_BASE}/preview?url=${encodeURIComponent(previewUrl)}`)
                .then(res => res.json())
                .then(data => {
                    if (data.error) {
                        previewTableWrapper.innerHTML = `<div style="text-align:center;padding:24px;color:var(--accent-red);">${data.error}</div>`;
                        return;
                    }
                    if (!data.columns || data.columns.length === 0) {
                        previewTableWrapper.innerHTML = `<div style="text-align:center;padding:24px;color:var(--text-secondary);">${trans.detailUnknown}</div>`;
                        return;
                    }
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
                    previewTableWrapper.innerHTML = html;
                })
                .catch(() => {
                    previewTableWrapper.innerHTML = `<div style="text-align:center;padding:24px;color:var(--accent-red);">${trans.toastError}</div>`;
                });
        });
        
        previewCloseBtn.addEventListener('click', () => {
            previewContainer.style.display = 'none';
        });
        
        // --- Start Download button click ---
        downloadBtn.addEventListener('click', () => {
            let downloadUrl = '';
            let targetName = dataset.name;
            
            if (dataset.source === 'kaggle') {
                downloadUrl = `kaggle:${dataset.item}`; // Special URL format for backend
                targetName = dataset.name;
            } else if (dataset.source === 'huggingface') {
                if (!selectedHfFile) {
                    showToast(trans.hfFileNotFound, true);
                    return;
                }
                downloadUrl = `https://huggingface.co/datasets/${dataset.item}/resolve/main/${selectedHfFile}`;
                const parts = selectedHfFile.split('/');
                const filename = parts[parts.length - 1];
                targetName = filename.replace(/\.[^/.]+$/, ""); // strip extension
            } else {
                // Rdataset
                downloadUrl = dataset.url;
                targetName = dataset.name.toLowerCase();
            }
            
            const targetDir = dirInput.value.trim();
            
            // UI Feedback: Disable button and show states
            downloadBtn.disabled = true;
            downloadBtn.textContent = trans.toastDownloading;
            
            if (selectedFormat === 'rdata' || selectedFormat === 'rds') {
                setTimeout(() => {
                    if (downloadBtn.disabled) {
                        downloadBtn.textContent = trans.toastConverting;
                    }
                }, 1000);
            }
            
            // API call to Python backend
            fetch(`${API_BASE}/download`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    url: downloadUrl,
                    dataset_name: targetName,
                    format: selectedFormat,
                    target_dir: targetDir
                })
            })
            .then(res => {
                if (!res.ok) {
                    return res.json().then(err => { throw new Error(err.error || 'Download error'); });
                }
                return res.json();
            })
            .then(data => {
                downloadBtn.textContent = trans.toastSuccess;
                downloadBtn.classList.add('success');
                showToast(`${trans.toastSuccess}: ${data.file_path}`);
                DatasetStorage.addRecentDownload(dataset, data.file_path, selectedFormat);

                setTimeout(() => {
                    downloadBtn.disabled = false;
                    downloadBtn.textContent = trans.detailDownloadBtn;
                    downloadBtn.classList.remove('success');
                }, 1500);
            })
            .catch(err => {
                downloadBtn.disabled = false;
                downloadBtn.textContent = trans.detailDownloadBtn;
                showToast(`${trans.toastError}: ${err.message}`, true);
            });
        });
}
