// Translations
// --- Translations Dictionary ---
const uiTranslations = {};
const uiTranslationsLoading = {};

function isValidTranslationPayload(data) {
    return data && typeof data === 'object' && !data.error_code && typeof data.title === 'string';
}

function loadTranslations(lang) {
    if (uiTranslations[lang] && isValidTranslationPayload(uiTranslations[lang])) {
        return Promise.resolve(uiTranslations[lang]);
    }
    if (uiTranslations[lang] && !isValidTranslationPayload(uiTranslations[lang])) {
        delete uiTranslations[lang];
    }
    if (uiTranslationsLoading[lang]) return uiTranslationsLoading[lang];

    uiTranslationsLoading[lang] = fetch(`${API_BASE}/translations?lang=${lang}`)
        .then(res => parseJsonResponse(res, { classify: true }))
        .then(data => {
            if (!isValidTranslationPayload(data)) {
                const err = new Error('Invalid translations payload');
                err.kind = 'server';
                throw err;
            }
            uiTranslations[lang] = data;
            return data;
        })
        .catch(async (err) => {
            if (lang !== 'en') {
                try {
                    return await loadTranslations('en');
                } catch (_) {}
            }
            throw err;
        })
        .finally(() => {
            delete uiTranslationsLoading[lang];
        });
    return uiTranslationsLoading[lang];
}

function applyCopyHintCssVar(lang) {
    const hint = uiTranslations[lang]?.copyHint || 'Click to copy';
    const escaped = hint.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
    document.documentElement.style.setProperty('--copy-hint-text', `"${escaped}"`);
}

// --- Language Switching Handler ---
function applyTranslations(lang) {
    if (!uiTranslations[lang]) return;
    
    // Toggle RTL/LTR
    if (lang === 'ar') {
        overlayContainer.setAttribute('dir', 'rtl');
    } else {
        overlayContainer.setAttribute('dir', 'ltr');
    }
    
    // Apply texts
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const key = el.getAttribute('data-i18n');
        const text = uiTranslations[lang][key];
        if (text) {
            if (key === 'searchPlaceholder') {
                el.placeholder = text;
            } else if (key.includes('_r') || key.includes('_p') || key.startsWith('kaggleStep') || key === 'kaggleSetupNote') {
                // Keep html tag styling for lists/code
                el.innerHTML = text;
            } else {
                el.textContent = text;
            }
        }
    });
    applyCopyHintCssVar(lang);
    updateOnboardingVisibility();
    updateThemeToggleButton();
    updateKaggleBanner();
    updateDatasetListA11y();
    updateCheatSheetA11y();
    syncFilterPillTabindex();
    if (typeof updateDownloadQueueUI === 'function') updateDownloadQueueUI();
    if (typeof renderDownloadHistoryPanel === 'function') renderDownloadHistoryPanel();
}

// Bind language switcher dropdown
function switchLanguage(lang) {
    currentLang = lang;
    localStorage.setItem('app_lang', currentLang);
    loadTranslations(currentLang)
        .then(() => {
            applyTranslations(currentLang);
            if (currentTab === 'datasets-tab') {
                if (selectedDataset) {
                    selectDataset(selectedDataset);
                } else {
                    triggerSearch(searchInput.value.trim());
                }
            }
        })
        .catch((err) => {
            const trans = uiTranslations.en || {};
            const message = err?.kind === 'rate_limit'
                ? (trans.rateLimitError || err.message)
                : (trans.connectionError || err.message || 'Error');
            showToast(message, true);
        });
}
