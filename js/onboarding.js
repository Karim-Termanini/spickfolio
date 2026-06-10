// First-launch onboarding and empty states
const ONBOARDING_DISMISSED_KEY = 'stats_sheets_onboarding_dismissed';

const EMPTY_STATE_ICONS = {
    search: '<svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><path d="M20 20l-3.5-3.5"></path></svg>',
    favorites: '<svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87L18.18 22 12 18.56 5.82 22 7 14.14l-5-4.87 6.91-1.01z"></path></svg>',
    recent: '<svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 3"></path></svg>',
    connection: '<svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><path d="M12 9v4M12 17h.01"></path></svg>',
    rateLimit: '<svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 3"></path></svg>',
};

const HTTP_ERROR_CONFIG = {
    rate_limit: { icon: 'rateLimit', titleKey: 'rateLimitError', hintKey: 'rateLimitHint', cssClass: 'empty-state-warn' },
    server: { icon: 'connection', titleKey: 'serverError', hintKey: 'serverErrorHint', cssClass: 'empty-state-error' },
    connection: { icon: 'connection', titleKey: 'connectionError', hintKey: 'connectionErrorHint', cssClass: 'empty-state-error' },
    client: { icon: 'connection', titleKey: 'searchError', hintKey: 'searchErrorHint', cssClass: 'empty-state-error' },
};

let activeErrorCountdown = null;

function clearErrorCountdown() {
    if (activeErrorCountdown) {
        clearInterval(activeErrorCountdown.id);
        activeErrorCountdown = null;
    }
}

function formatRateLimitRetry(trans, seconds) {
    const template = trans.rateLimitRetryIn || 'Retry in {seconds}s';
    return template.replace('{seconds}', String(seconds));
}

function bindRetryButton(btn, trans, retryLabel, onRetry) {
    btn.addEventListener('click', () => {
        btn.disabled = true;
        btn.textContent = trans.connectionRetrying || 'Retrying...';
        Promise.resolve(onRetry()).catch(() => {}).finally(() => {
            btn.disabled = false;
            btn.textContent = retryLabel;
        });
    });
}

function startRateLimitCountdown(btn, seconds, trans, retryLabel, onRetry) {
    let remaining = Math.max(1, Math.floor(seconds));
    btn.disabled = true;
    btn.textContent = formatRateLimitRetry(trans, remaining);

    clearErrorCountdown();
    const id = setInterval(() => {
        remaining -= 1;
        if (remaining <= 0) {
            clearErrorCountdown();
            btn.disabled = false;
            btn.textContent = retryLabel;
            bindRetryButton(btn, trans, retryLabel, onRetry);
            return;
        }
        btn.textContent = formatRateLimitRetry(trans, remaining);
    }, 1000);
    activeErrorCountdown = { id };
}

const EMPTY_STATE_CONFIG = {
    search: { icon: 'search', titleKey: 'noDatasets', hintKey: 'emptyHintSearch' },
    favorites: { icon: 'favorites', titleKey: 'noFavorites', hintKey: 'emptyHintFavorites' },
    recent: { icon: 'recent', titleKey: 'noRecents', hintKey: 'emptyHintRecent' },
};

function renderEmptyState(container, variant) {
    const config = EMPTY_STATE_CONFIG[variant] || EMPTY_STATE_CONFIG.search;
    const trans = uiTranslations[currentLang] || {};
    const title = trans[config.titleKey] || '';
    const hint = trans[config.hintKey] || '';
    container.innerHTML = `
        <div class="empty-state" data-variant="${variant}">
            <div class="empty-state-icon">${EMPTY_STATE_ICONS[config.icon]}</div>
            <p class="empty-state-title">${escapeHtml(title)}</p>
            <p class="empty-state-hint">${escapeHtml(hint)}</p>
        </div>`;
}

function renderHttpErrorState(container, kind, onRetry, options = {}) {
    clearErrorCountdown();
    const config = HTTP_ERROR_CONFIG[kind] || HTTP_ERROR_CONFIG.server;
    const trans = uiTranslations[currentLang] || {};
    const title = trans[config.titleKey] || 'Error';
    const hint = trans[config.hintKey] || '';
    const retryLabel = trans.connectionRetry || 'Retry';
    container.innerHTML = `
        <div class="empty-state ${config.cssClass}">
            <div class="empty-state-icon">${EMPTY_STATE_ICONS[config.icon]}</div>
            <p class="empty-state-title">${escapeHtml(title)}</p>
            <p class="empty-state-hint">${escapeHtml(hint)}</p>
            <button type="button" class="empty-state-retry">${escapeHtml(retryLabel)}</button>
        </div>`;
    const btn = container.querySelector('.empty-state-retry');
    if (!btn || typeof onRetry !== 'function') return;

    if (kind === 'rate_limit') {
        const retryAfter = options.retryAfter ?? DEFAULT_RATE_LIMIT_RETRY_SECONDS;
        startRateLimitCountdown(btn, retryAfter, trans, retryLabel, onRetry);
        return;
    }

    bindRetryButton(btn, trans, retryLabel, onRetry);
}

function renderConnectionErrorState(container, onRetry) {
    renderHttpErrorState(container, 'connection', onRetry);
}

function classifySearchFailure(err) {
    if (err?.kind) return err.kind;
    if (err instanceof TypeError || err?.message === 'Failed to fetch') return 'connection';
    return 'server';
}

async function parseSearchResponse(res) {
    return parseJsonResponse(res, { classify: true });
}

function isOnboardingDismissed() {
    try {
        return localStorage.getItem(ONBOARDING_DISMISSED_KEY) === '1';
    } catch {
        return false;
    }
}

function updateOnboardingVisibility() {
    const banner = document.getElementById('onboardingBanner');
    if (!banner) return;
    banner.hidden = isOnboardingDismissed();
}

function initOnboarding() {
    const banner = document.getElementById('onboardingBanner');
    const btn = document.getElementById('dismissOnboardingBtn');
    if (!banner || !btn) return;

    btn.addEventListener('click', () => {
        banner.hidden = true;
        try {
            localStorage.setItem(ONBOARDING_DISMISSED_KEY, '1');
        } catch (e) {}
    });

    updateOnboardingVisibility();
}
