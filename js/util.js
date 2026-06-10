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
    const raw = String(size).trim();
    if (/^\d+$/.test(raw)) {
        const n = Number(raw);
        return Number.isFinite(n) && n > 0 ? n : null;
    }
    const normalized = raw.replace(/,/g, '');
    const match = normalized.match(/^([\d.]+)\s*(B|KB|MB|GB|TB)?$/i);
    if (!match) return null;
    const value = Number(match[1]);
    if (!Number.isFinite(value) || value <= 0) return null;
    const unit = (match[2] || 'B').toUpperCase();
    const multipliers = {
        B: 1,
        KB: 1024,
        MB: 1048576,
        GB: 1073741824,
        TB: 1099511627776,
    };
    const mult = multipliers[unit];
    if (!mult) return null;
    return Math.floor(value * mult);
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

const DEFAULT_RATE_LIMIT_RETRY_SECONDS = 60;

function parseRetryAfter(res) {
    const header = res.headers.get('Retry-After');
    if (header) {
        const seconds = parseInt(header, 10);
        if (!Number.isNaN(seconds) && seconds > 0) return seconds;
    }
    return DEFAULT_RATE_LIMIT_RETRY_SECONDS;
}

async function parseJsonResponse(res, { classify = false } = {}) {
    const data = await res.json().catch(() => ({}));
    if (res.status === 429) {
        const err = new Error(resolveApiError(
            { error_code: data.error_code || 'rate_limit', error: data.error },
            'rateLimitError',
        ));
        if (classify) err.kind = 'rate_limit';
        err.retryAfter = parseRetryAfter(res);
        throw err;
    }
    if (!res.ok) {
        const err = new Error(resolveApiError(data, 'toastError'));
        if (classify) {
            err.kind = res.status >= 500 ? 'server' : 'client';
            err.status = res.status;
        }
        throw err;
    }
    return data;
}
