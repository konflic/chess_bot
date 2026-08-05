(function () {
    const board = document.getElementById('bs-placement-board');
    if (!board) return;

    const placedShips = [];
    let remaining = JSON.parse(board.dataset.remaining || '[]');
    let currentLength = remaining[0] || null;
    let orientation = 'h';

    const cellsEl = {};
    board.querySelectorAll('.bs-cell').forEach(td => {
        cellsEl[td.dataset.cell] = td;
    });

    const infoEl = document.getElementById('bs-place-info');
    const orientEl = document.getElementById('bs-orientation');
    const rotateBtn = document.getElementById('bs-rotate-btn');
    const lockBtn = document.getElementById('bs-lock-btn');

    function render() {
        if (!currentLength) {
            infoEl.textContent = 'All ships placed!';
        } else {
            const count = remaining.filter(l => l === currentLength).length;
            infoEl.textContent = 'Ship length: ' + currentLength + (count > 1 ? ' (x' + count + ')' : '');
        }
        orientEl.textContent = orientation === 'h' ? 'Horizontal' : 'Vertical';
        lockBtn.disabled = remaining.length > 0;
    }

    function shipCells(cell, length, ori) {
        const col = cell.charCodeAt(0);
        const row = parseInt(cell.slice(1), 10);
        const cells = [];
        for (let i = 0; i < length; i++) {
            cells.push(ori === 'h' ? String.fromCharCode(col + i) + row : cell[0] + (row + i));
        }
        return cells;
    }

    function canPlace(cells) {
        const occupied = new Set(placedShips.flat());
        for (const c of cells) {
            if (!cellsEl[c] || occupied.has(c)) return false;
        }
        return true;
    }

    board.querySelectorAll('.bs-cell').forEach(td => {
        td.addEventListener('click', () => {
            if (!currentLength) return;
            const cells = shipCells(td.dataset.cell, currentLength, orientation);
            if (!canPlace(cells)) {
                infoEl.textContent = 'Cannot place ship here';
                return;
            }
            placedShips.push(cells);
            remaining.splice(remaining.indexOf(currentLength), 1);
            cells.forEach(c => cellsEl[c].classList.add('ship'));
            currentLength = remaining[0] || null;
            render();
        });
    });

    if (rotateBtn) {
        rotateBtn.addEventListener('click', () => {
            orientation = orientation === 'h' ? 'v' : 'h';
            render();
        });
    }

    lockBtn.addEventListener('click', () => {
        document.getElementById('bs-fleet-json').value = JSON.stringify(placedShips);
    });

    render();
})();
