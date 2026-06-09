// Bootstrap
initTheme();
applyLaunchModeUi();

if (servedFromServer) {
    initializeApp(window.location.origin);
} else if (explicitPort) {
    initializeApp(explicitPort);
} else {
    initializeApp(18700);
}

startHeartbeat();

if (languageSelect) {
    languageSelect.value = currentLang;
    languageSelect.addEventListener('change', () => {
        switchLanguage(languageSelect.value);
    });
