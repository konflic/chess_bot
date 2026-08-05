"""Pure battleship rules — no storage, no web.

The classic Russian "Sea Battle":
- 10x10 grid, rows numbered 1-10, columns lettered A-J
- fleet: one 4-cell, two 3-cell, three 2-cell and four 1-cell ships
- ships may touch, but may not overlap

A fleet is a list of ships; each ship is a list of cell strings, e.g.
[["A1", "A2", "A3", "A4"], ["B2", "B3"], ...]. Shots are a dict mapping
a cell string to "hit" or "miss".
"""

BOARD_SIZE = 10
COLS = "ABCDEFGHIJ"
FLEET = [4, 3, 3, 2, 2, 2, 1, 1, 1, 1]
FLEET_COUNTS = {length: FLEET.count(length) for length in sorted(set(FLEET))}


def cell_to_rc(cell):
    """'A1' -> (row, col). Returns None if the cell is invalid."""
    cell = (cell or "").strip().upper()
    if len(cell) < 2:
        return None
    col = COLS.find(cell[0])
    if col < 0:
        return None
    try:
        row = int(cell[1:])
    except ValueError:
        return None
    if not 1 <= row <= BOARD_SIZE:
        return None
    return row - 1, col


def rc_to_cell(row, col):
    return f"{COLS[col]}{row + 1}"


def fleet_cells(ships):
    return {cell for ship in ships for cell in ship}


def validate_fleet(ships):
    """Check a fleet against the rules.

    Returns (ok, error).
    """
    if not isinstance(ships, list) or not ships:
        return False, "Fleet must be a non-empty list of ships"

    if not all(
        isinstance(ship, list) and all(isinstance(cell, str) for cell in ship)
        for ship in ships
    ):
        return False, "Invalid cell coordinates"

    if sorted(len(ship) for ship in ships) != sorted(FLEET):
        return False, (
            "Fleet must contain one 4-cell, two 3-cell, three 2-cell "
            "and four 1-cell ships"
        )

    seen = set()
    for ship in ships:
        cells = [cell_to_rc(cell) for cell in ship]
        if any(cell is None for cell in cells):
            return False, "Invalid cell coordinates"

        if len(cells) > 1:
            rows = {r for r, _ in cells}
            cols = {c for _, c in cells}
            if len(rows) > 1 and len(cols) > 1:
                return False, "Ships must be placed in a straight line"
            if len(rows) == 1:
                ordered = sorted(c for _, c in cells)
            else:
                ordered = sorted(r for r, _ in cells)
            if ordered != list(range(ordered[0], ordered[0] + len(ordered))):
                return False, "Ship cells must be adjacent"

        for rc in cells:
            if rc in seen:
                return False, "Ships must not overlap"
            seen.add(rc)

    return True, None


def ships_remaining(ships, shots):
    return sum(
        1 for ship in ships if not all(shots.get(cell) == "hit" for cell in ship)
    )


def apply_shot(ships, shots, cell):
    """Fire at a cell on a fleet.

    Mutates shots (adds the shot) and returns a dict with either an error
    or {result: 'hit'|'miss', sunk: list-of-cells-or-None, ships_left}.
    """
    if cell_to_rc(cell) is None:
        return {"error": "Invalid cell"}

    cell = cell.strip().upper()
    if cell in shots:
        return {"error": "Cell already shot"}

    cells = fleet_cells(ships)
    if cell in cells:
        shots[cell] = "hit"
        sunk = None
        for ship in ships:
            if cell in ship and all(
                shots.get(c) == "hit" for c in ship
            ):
                sunk = list(ship)
                break
    else:
        shots[cell] = "miss"

    return {
        "result": "hit" if shots[cell] == "hit" else "miss",
        "sunk": sunk if shots[cell] == "hit" else None,
        "ships_left": ships_remaining(ships, shots),
    }
