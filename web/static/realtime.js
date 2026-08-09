(function () {
    const gameId = document.body && document.body.dataset.gameId;
    if (!gameId) return;

    window.__posting = false;
    document.addEventListener('submit', function () {
        window.__posting = true;
    }, true);

    const es = new EventSource('/events/game/' + gameId);
    es.onmessage = function () {
        if (window.__posting) return;
        window.location.reload();
    };
})();
