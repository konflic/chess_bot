"""Pure rules checks: battleship fleet validation, coordinates, shots.

Run:  python tests/core_rules.py
"""

import sys

sys.path.insert(0, "/home/chirkov/Develop/chess_bot")
sys.path.insert(0, "/home/chirkov/Develop/chess_bot/tests")

from common import VALID_FLEET
from core import battleship


def run():
    ok, err = battleship.validate_fleet(VALID_FLEET)
    assert ok and err is None, "valid fleet rejected"

    bad = VALID_FLEET[:9]
    ok, _ = battleship.validate_fleet(bad)
    assert ok is False, "wrong fleet size accepted"

    bad2 = [list(VALID_FLEET[0])] + VALID_FLEET[1:]
    bad2[0] = ["A1", "A2", "A3", "A5"]
    ok, _ = battleship.validate_fleet(bad2)
    assert ok is False, "non-contiguous ship accepted"

    bad3 = [list(VALID_FLEET[0])] + VALID_FLEET[1:]
    bad3[0] = ["A1", "B1", "C1", "A2"]
    ok, _ = battleship.validate_fleet(bad3)
    assert ok is False, "overlap accepted"

    assert battleship.cell_to_rc("A1") == (0, 0)
    assert battleship.cell_to_rc("J10") == (9, 9)
    assert battleship.cell_to_rc("K1") is None
    assert battleship.cell_to_rc("A11") is None
    assert battleship.rc_to_cell(0, 0) == "A1"
    assert battleship.fleet_cells(VALID_FLEET) == {c for ship in VALID_FLEET for c in ship}

    shots = {}
    out = battleship.apply_shot(VALID_FLEET, shots, "A1")
    assert out["result"] == "hit" and out["ships_left"] == 10 and out["sunk"] is None, out
    out = battleship.apply_shot(VALID_FLEET, shots, "A2")
    assert out["result"] == "hit" and out["sunk"] is None, out
    out = battleship.apply_shot(VALID_FLEET, shots, "A3")
    assert out["result"] == "hit" and out["sunk"] is None, out
    out = battleship.apply_shot(VALID_FLEET, shots, "A4")
    assert out["result"] == "hit" and out["sunk"] == ["A1", "A2", "A3", "A4"] and out["ships_left"] == 9, out
    out = battleship.apply_shot(VALID_FLEET, shots, "A9")
    assert out["result"] == "miss" and out["ships_left"] == 9, out
    assert battleship.apply_shot(VALID_FLEET, shots, "A1")["error"], "double shot allowed"
    assert battleship.apply_shot(VALID_FLEET, shots, "Q1")["error"], "off-board shot allowed"

    print("core_rules: OK")


if __name__ == "__main__":
    run()
