/**
 * Favorites and recent downloads (localStorage).
 */
const DatasetStorage = (() => {
    const LS_FAVORITES = 'spickfolio_favorites';
    const LS_RECENTS = 'spickfolio_recent_downloads';
    const LS_TARGET_BY_SOURCE = 'spickfolio_target_dir_by_source';
    const LS_FORMAT_BY_SOURCE = 'spickfolio_format_by_source';

    function migrateStorageKey(oldKey, newKey) {
        try {
            if (localStorage.getItem(newKey) == null && localStorage.getItem(oldKey) != null) {
                localStorage.setItem(newKey, localStorage.getItem(oldKey));
            }
        } catch (_) {}
    }

    [
        ['stats_sheets_favorites', LS_FAVORITES],
        ['stats_sheets_recent_downloads', LS_RECENTS],
        ['stats_sheets_target_dir_by_source', LS_TARGET_BY_SOURCE],
        ['stats_sheets_format_by_source', LS_FORMAT_BY_SOURCE],
        ['spick_folio_favorites', LS_FAVORITES],
        ['spick_folio_recent_downloads', LS_RECENTS],
        ['spick_folio_target_dir_by_source', LS_TARGET_BY_SOURCE],
        ['spick_folio_format_by_source', LS_FORMAT_BY_SOURCE],
    ].forEach(([from, to]) => migrateStorageKey(from, to));
    const VALID_FORMATS = ['csv', 'json', 'rdata', 'rds'];
    const MAX_RECENTS = 20;

    function loadFavorites() {
        try {
            return JSON.parse(localStorage.getItem(LS_FAVORITES) || '[]');
        } catch {
            return [];
        }
    }

    function saveFavorites(list) {
        localStorage.setItem(LS_FAVORITES, JSON.stringify(list));
    }

    function isFavorite(datasetId) {
        return loadFavorites().some(f => f.id === datasetId);
    }

    function toggleFavorite(dataset) {
        let list = loadFavorites();
        const idx = list.findIndex(f => f.id === dataset.id);
        if (idx >= 0) {
            list.splice(idx, 1);
            saveFavorites(list);
            return false;
        }
        list.unshift({ ...dataset });
        saveFavorites(list);
        return true;
    }

    function loadRecentDownloads() {
        try {
            return JSON.parse(localStorage.getItem(LS_RECENTS) || '[]');
        } catch {
            return [];
        }
    }

    function csvEscape(val) {
        const s = String(val ?? '');
        if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
        return s;
    }

    function exportRecentDownloadsCsv() {
        const entries = loadRecentDownloads();
        if (!entries.length) return false;

        const headers = ['name', 'id', 'source', 'package', 'item', 'format', 'file_path', 'downloaded_at'];
        const rows = entries.map(entry => {
            const ds = entry.dataset || {};
            return [
                ds.name || ds.title || '',
                ds.id || '',
                ds.source || '',
                ds.package || '',
                ds.item || '',
                entry.format || '',
                entry.file_path || '',
                entry.at ? new Date(entry.at).toISOString() : '',
            ].map(csvEscape).join(',');
        });

        const csv = [headers.join(','), ...rows].join('\n');
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `spickfolio-recent-downloads-${new Date().toISOString().slice(0, 10)}.csv`;
        a.click();
        URL.revokeObjectURL(url);
        return true;
    }

    function addRecentDownload(dataset, filePath, format, pathIsDir) {
        let list = loadRecentDownloads();
        list = list.filter(r => r.dataset?.id !== dataset.id);
        list.unshift({
            dataset: { ...dataset },
            file_path: filePath,
            format,
            path_is_dir: !!pathIsDir,
            at: Date.now(),
        });
        if (list.length > MAX_RECENTS) {
            list = list.slice(0, MAX_RECENTS);
        }
        localStorage.setItem(LS_RECENTS, JSON.stringify(list));
    }

    function getRecentDatasetsForList() {
        return loadRecentDownloads().map(entry => ({
                ...entry.dataset,
                _recentPath: entry.file_path,
                _recentFormat: entry.format,
                _recentAt: entry.at,
        }));
    }

    function filterByQuery(list, query) {
        if (!query) return list;
        const q = query.toLowerCase();
        return list.filter(ds =>
            (ds.name || '').toLowerCase().includes(q) ||
            (ds.title || '').toLowerCase().includes(q) ||
            (ds.package || '').toLowerCase().includes(q) ||
            (ds.item || '').toLowerCase().includes(q)
        );
    }

    function paginate(list, page, perPage) {
        const total = list.length;
        const totalPages = Math.max(1, Math.ceil(total / perPage) || 1);
        const start = (page - 1) * perPage;
        return {
            results: list.slice(start, start + perPage),
            total,
            total_pages: totalPages,
        };
    }

    function loadTargetDirBySource() {
        try {
            return JSON.parse(localStorage.getItem(LS_TARGET_BY_SOURCE) || '{}');
        } catch {
            return {};
        }
    }

    function getTargetDirForSource(source, fallbackDir) {
        const map = loadTargetDirBySource();
        const saved = map[source];
        if (saved && String(saved).trim()) return String(saved).trim();
        const last = localStorage.getItem('last_target_dir');
        if (last && String(last).trim()) return String(last).trim();
        return fallbackDir || '';
    }

    function saveTargetDirForSource(source, path) {
        if (!source) return;
        const map = loadTargetDirBySource();
        map[source] = String(path || '').trim();
        localStorage.setItem(LS_TARGET_BY_SOURCE, JSON.stringify(map));
    }

    function loadFormatBySource() {
        try {
            return JSON.parse(localStorage.getItem(LS_FORMAT_BY_SOURCE) || '{}');
        } catch {
            return {};
        }
    }

    function getFormatForSource(source) {
        const map = loadFormatBySource();
        const fmt = map[source];
        return VALID_FORMATS.includes(fmt) ? fmt : 'csv';
    }

    function saveFormatForSource(source, format) {
        if (!source || !VALID_FORMATS.includes(format)) return;
        const map = loadFormatBySource();
        map[source] = format;
        localStorage.setItem(LS_FORMAT_BY_SOURCE, JSON.stringify(map));
    }

    return {
        loadFavorites,
        loadRecentDownloads,
        isFavorite,
        toggleFavorite,
        addRecentDownload,
        getRecentDatasetsForList,
        exportRecentDownloadsCsv,
        filterByQuery,
        paginate,
        getTargetDirForSource,
        saveTargetDirForSource,
        getFormatForSource,
        saveFormatForSource,
    };
})();
