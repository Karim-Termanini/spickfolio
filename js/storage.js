/**
 * Favorites and recent downloads (localStorage).
 */
const DatasetStorage = (() => {
    const LS_FAVORITES = 'stats_sheets_favorites';
    const LS_RECENTS = 'stats_sheets_recent_downloads';
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

    function addRecentDownload(dataset, filePath, format) {
        let list = [];
        try {
            list = JSON.parse(localStorage.getItem(LS_RECENTS) || '[]');
        } catch {
            list = [];
        }
        list = list.filter(r => r.dataset?.id !== dataset.id);
        list.unshift({
            dataset: { ...dataset },
            file_path: filePath,
            format,
            at: Date.now(),
        });
        if (list.length > MAX_RECENTS) {
            list = list.slice(0, MAX_RECENTS);
        }
        localStorage.setItem(LS_RECENTS, JSON.stringify(list));
    }

    function getRecentDatasetsForList() {
        try {
            return JSON.parse(localStorage.getItem(LS_RECENTS) || '[]').map(entry => ({
                ...entry.dataset,
                _recentPath: entry.file_path,
                _recentFormat: entry.format,
                _recentAt: entry.at,
            }));
        } catch {
            return [];
        }
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

    return {
        loadFavorites,
        isFavorite,
        toggleFavorite,
        addRecentDownload,
        getRecentDatasetsForList,
        filterByQuery,
        paginate,
    };
})();
