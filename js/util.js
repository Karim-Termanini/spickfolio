// Shared DOM/string helpers (load before modules that render HTML)
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text ?? '';
    return div.innerHTML;
}

function escapeAttr(str) {
    return String(str ?? '')
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

const KAGGLE_PREVIEW_MAX_BYTES = 50 * 1024 * 1024;

function parseKaggleSizeBytes(size) {
    if (size == null || size === '') return null;
    const digits = String(size).replace(/[^\d]/g, '');
    if (!digits) return null;
    const n = Number(digits);
    return Number.isFinite(n) && n > 0 ? n : null;
}

function isKagglePreviewAllowed(dataset) {
    const bytes = parseKaggleSizeBytes(dataset?.size);
    if (bytes == null) return true;
    return bytes <= KAGGLE_PREVIEW_MAX_BYTES;
}

function resolveApiError(data, fallbackKey) {
    const trans = uiTranslations[currentLang] || {};
    if (data?.error_code && trans[data.error_code]) return trans[data.error_code];
    if (data?.error) return data.error;
    return trans[fallbackKey] || trans.toastError || 'Error';
}
