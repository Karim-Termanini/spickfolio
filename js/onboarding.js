// First-launch onboarding and empty states
const ONBOARDING_DISMISSED_KEY = 'stats_sheets_onboarding_dismissed';

const EMPTY_STATE_ICONS = {
    search: '<svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><path d="M20 20l-3.5-3.5"></path></svg>',
    favorites: '<svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87L18.18 22 12 18.56 5.82 22 7 14.14l-5-4.87 6.91-1.01z"></path></svg>',
    recent: '<svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 3"></path></svg>',
    connection: '<svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><path d="M12 9v4M12 17h.01"></path></svg>',
};

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

function renderConnectionErrorState(container, onRetry) {
    const trans = uiTranslations[currentLang] || {};
    const title = trans.connectionError || 'Connection error';
    const hint = trans.connectionErrorHint || 'Check that the server is running and try again.';
    const retryLabel = trans.connectionRetry || 'Retry';
    container.innerHTML = `
        <div class="empty-state empty-state-error">
            <div class="empty-state-icon">${EMPTY_STATE_ICONS.connection}</div>
            <p class="empty-state-title">${escapeHtml(title)}</p>
            <p class="empty-state-hint">${escapeHtml(hint)}</p>
            <button type="button" class="empty-state-retry">${escapeHtml(retryLabel)}</button>
        </div>`;
    const btn = container.querySelector('.empty-state-retry');
    if (!btn || typeof onRetry !== 'function') return;
    btn.addEventListener('click', () => {
        btn.disabled = true;
        btn.textContent = trans.connectionRetrying || 'Retrying...';
        Promise.resolve(onRetry()).catch(() => {}).finally(() => {
            btn.disabled = false;
            btn.textContent = retryLabel;
        });
    });
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
