// Translations
// --- Translations Dictionary ---
const uiTranslations = {};
const uiTranslationsLoading = {};

function loadTranslations(lang) {
    if (uiTranslations[lang]) return Promise.resolve(uiTranslations[lang]);
    if (uiTranslationsLoading[lang]) return uiTranslationsLoading[lang];
    uiTranslationsLoading[lang] = fetch(`${API_BASE}/translations?lang=${lang}`)
        .then(res => res.json())
        .then(data => {
            uiTranslations[lang] = data;
            delete uiTranslationsLoading[lang];
            return data;
        })
        .catch(() => {
            delete uiTranslationsLoading[lang];
            return {};
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
            } else if (key.includes('_r') || key.includes('_p') || key === 'kaggleBanner') {
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
    updateDatasetListA11y();
    updateCheatSheetA11y();
    syncFilterPillTabindex();
}

// Bind language switcher dropdown
function switchLanguage(lang) {
    currentLang = lang;
    localStorage.setItem('app_lang', currentLang);
    loadTranslations(currentLang).then(() => {
        applyTranslations(currentLang);
        if (currentTab === 'datasets-tab') {
            if (selectedDataset) {
                selectDataset(selectedDataset);
            } else {
                triggerSearch(searchInput.value.trim());
            }
        }
    });
}
