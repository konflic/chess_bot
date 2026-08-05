import asyncio
import datetime
import json
import os
from urllib.parse import urlencode
import chess
import chess.svg
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from core import battleship
from core.battleship_manager import BattleshipManager
from core.game_manager import ChessGameManager
from configuration import APP_VERSION

LOCALES = {"en", "ru"}


def _translate(lang: str, key: str, **kwargs: str) -> str:
    text = TRANSLATIONS.get(lang, {}).get(key, key)
    if kwargs:
        return text % kwargs
    return text


def _get_lang(request: Request) -> str:
    lang = request.cookies.get("lang", "en")
    return lang if lang in LOCALES else "en"


TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {},
    "ru": {
        "Game: %(id)s": "Игра: %(id)s",
        "Waiting for opponent": "Ожидание соперника",
        "Playing": "Игра",
        "Finished": "Завершена",
        "Are you sure you want to give up? The game will be ended and your opponent will win.":
            "Вы уверены, что хотите сдаться? Игра завершится, и ваш соперник победит.",
        "Give Up": "Сдаться",
        "You play as %(color)s": "Ваши %(color)s",
        "Move": "Ход",
        "Waiting for opponent...": "Ожидание соперника...",
        "Refresh": "Обновить",
        "Your opponent gave up — you win!": "Соперник сдался — вы победили!",
        "You gave up — opponent wins.": "Вы сдались — победа соперника.",
        "Game ended — one player gave up.": "Игра завершена — игрок сдался.",
        "Game ended in a draw!": "Игра закончилась ничьей!",
        "You win!": "Вы победили!",
        "You lose!": "Вы проиграли!",
        "Game ended.": "Игра завершена.",
        "Moves": "Ходы",
        "WHITE": "БЕЛЫЕ",
        "BLACK": "ЧЕРНЫЕ",
        "TIME": "ВРЕМЯ",
        "No moves yet.": "Ходов пока нет.",
        "Share this link with a friend to invite them:": "Отправьте эту ссылку другу, чтобы пригласить его:",
        "Copy": "Копировать",
        "Spectator link — share so others can watch:": "Ссылка для зрителей",
        "Choose a game": "Выберите игру",
        "Play chess with friends": "Играйте в шахматы с друзьями",
        "Create New Game": "Новая игра",
        "Share the game link with a friend to play together.":
            "Отправьте ссылку другу, чтобы играть вместе.",
        "Games expire 24 hours after creation.":
            "Игры удаляются через 24 часа после создания.",
        "Join Game": "Присоединиться к игре",
        "Home": "На главную",
        "You were invited to a game!": "Вас пригласили в игру!",
        "You will play as Black.": "Вы играете чёрными.",
        "Join as Black": "Присоединиться",
        "Game ended — %(winner)s won by checkmate!":
            "Игра завершена — %(winner)s выиграл(а) матом!",
        "white": "белые",
        "black": "чёрные",
        "Copied!": "Скопировано!",
        "Chess": "Шахматы",
        "Battleship": "Морской бой",
        "Play battleship with friends": "Играйте в морской бой с друзьями",
        "Place your ships": "Расставьте корабли",
        "Click a cell to place your ships, then lock the fleet.":
            "Нажимайте на клетки, чтобы расставить корабли, затем нажмите «Готов к бою».",
        "Ship length: %(len)s": "Корабль длиной: %(len)s",
        "Rotate": "Повернуть",
        "Horizontal": "Горизонтально",
        "Vertical": "Вертикально",
        "Lock Fleet": "Готов к бою",
        "All ships placed!": "Все корабли расставлены!",
        "Cannot place ship here": "Здесь нельзя разместить корабль",
        "Click a cell to shoot": "Кликните по клетке, чтобы выстрелить",
        "Your board": "Ваше поле",
        "Enemy board": "Поле противника",
        "Shots": "Выстрелы",
        "No shots yet.": "Выстрелов пока нет.",
        "Your turn": "Ваш ход",
        "Place your ships and lock your fleet.":
            "Расставьте корабли и нажмите «Готов к бою».",
        "Waiting for opponent to lock their fleet...":
            "Ожидание расстановки кораблей соперника...",
        "You locked your fleet.": "Вы расставили корабли.",
        "Opponent locked their fleet.": "Соперник расставил корабли.",
        "Game ended — all %(winner)s ships are sunk!":
            "Игра завершена — все корабли %(winner)s потоплены!",
        "Player A": "Игрок A",
        "Player B": "Игрок B",
        "You play as %(side)s": "Вы играете за %(side)s",
        "hit": "попадание",
        "miss": "мимо",
        "sunk": "потоплен",
        "shot_hit": "Попадание!",
        "shot_miss": "Мимо!",
        "shot_win": "Все корабли противника потоплены!",
        "fleet_locked": "Флот зафиксирован!",
        "gave_up": "Вы сдались.",
    },
}

# English translations are identity (keys are already English)
for key in TRANSLATIONS["ru"]:
    if key not in TRANSLATIONS["en"]:
        TRANSLATIONS["en"][key] = key

# Fill missing English keys as identity
for key in list(TRANSLATIONS["ru"].keys()):
    if key not in TRANSLATIONS["en"]:
        TRANSLATIONS["en"][key] = key

# Flash-token messages need real English (their key is not English)
TRANSLATIONS["en"].update({
    "shot_hit": "Hit!",
    "shot_miss": "Miss!",
    "shot_win": "All enemy ships sunk!",
    "fleet_locked": "Fleet locked!",
    "gave_up": "You gave up.",
})

HERE = os.path.dirname(__file__)

gm = ChessGameManager()
bsm = BattleshipManager()


COPY_ICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>'
    '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>'
)


def _nav_for(request: Request) -> str:
    path = request.url.path
    if path == "/":
        return "home"
    if path.startswith("/battleship"):
        return "battleship"
    return "chess"


def _common_context(request: Request) -> dict:
    lang = _get_lang(request)
    return {
        "lang": lang,
        "_": lambda key, **kw: _translate(lang, key, **kw),
        "copyIcon": COPY_ICON_SVG,
        "nav": _nav_for(request),
        "app_version": APP_VERSION,
    }


def _time_left(expires_at: str) -> str:
    expires = datetime.datetime.fromisoformat(expires_at)
    remaining = expires - datetime.datetime.utcnow()
    if remaining.total_seconds() > 0:
        hours = int(remaining.total_seconds() // 3600)
        minutes = int((remaining.total_seconds() % 3600) // 60)
        return f"{hours}h {minutes:02d}min"
    return "Expired"


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()

app = FastAPI(title="GameZZ Web", lifespan=lifespan)
templates = Jinja2Templates(directory=os.path.join(HERE, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")


async def _cleanup_loop():
    while True:
        await asyncio.sleep(300)
        deleted = gm.cleanup_expired()
        if deleted:
            print(f"[cleanup] removed {deleted} expired game(s)")


def _render_svg(fen: str) -> str:
    board = chess.Board(fen)
    return chess.svg.board(board=board, size=400, coordinates=True)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    ctx = _common_context(request)
    ctx.update({"request": request})
    return templates.TemplateResponse("index.html", ctx)


@app.get("/chess", response_class=HTMLResponse)
async def chess_index(request: Request):
    ctx = _common_context(request)
    ctx.update({"request": request})
    return templates.TemplateResponse("chess_index.html", ctx)


@app.post("/games/create")
async def create_game(request: Request):
    game_id, white_token, join_token = gm.create_web_game()
    return RedirectResponse(
        url=f"/game/{game_id}?player={white_token}",
        status_code=303,
    )


@app.post("/lang/{lang}")
async def set_lang(request: Request, lang: str):
    if lang not in LOCALES:
        lang = "en"
    next_url = request.headers.get("Referer", "/")
    resp = RedirectResponse(url=next_url, status_code=303)
    resp.set_cookie(key="lang", value=lang, max_age=365 * 24 * 3600)
    return resp


@app.get("/game/{game_id}", response_class=HTMLResponse)
async def game_page(request: Request, game_id: str, player: str | None = None):
    web_game = gm.get_web_game(game_id)
    if not web_game:
        ctx = _common_context(request)
        ctx.update({"request": request, "error": "Game not found or expired."})
        return templates.TemplateResponse("game.html", ctx, status_code=404)

    msg = request.query_params.get("msg")
    error = request.query_params.get("error")

    time_left = _time_left(web_game["expires_at"])

    svg = _render_svg(web_game["fen"])
    moves = gm.get_web_moves(game_id, web_game["created_at"])
    web_player = gm.get_web_player(player) if player else None

    my_color = None
    is_my_turn = False
    share_link = None
    is_creator = False

    if web_player and web_player["game_id"] == game_id:
        my_color = web_player["color"]
        board = chess.Board(web_game["fen"])
        turn_color = "white" if board.turn == chess.WHITE else "black"
        is_my_turn = web_game["status"] == "playing" and my_color == turn_color

    base_url = str(request.base_url).rstrip("/")
    spectator_link = f"{base_url}/game/{game_id}"

    if web_game["status"] == "waiting":
        join_token_row = gm.get_unused_join_token(game_id)
        if join_token_row:
            share_link = f"{base_url}/game/{game_id}/join?token={join_token_row}"
            if web_player and web_player["color"] == "white":
                is_creator = True

    ctx = _common_context(request)
    ctx.update({
        "request": request,
        "game_id": game_id,
        "game_status": web_game["status"],
        "fen": web_game["fen"],
        "svg": svg,
        "moves": moves,
        "my_color": my_color,
        "is_my_turn": is_my_turn,
        "player_token": player,
        "share_link": share_link,
        "is_creator": is_creator,
        "winner": web_game.get("winner"),
        "result_reason": web_game.get("result_reason"),
        "time_left": time_left,
        "spectator_link": spectator_link,
        "msg": msg,
        "error": error,
    })
    return templates.TemplateResponse("game.html", ctx)


@app.get("/game/{game_id}/join", response_class=HTMLResponse)
async def join_page(request: Request, game_id: str, token: str):
    game, err = gm.validate_join_token(token)
    ctx = _common_context(request)
    if err:
        ctx.update({"request": request, "error": err})
        return templates.TemplateResponse("join.html", ctx)
    ctx.update({"request": request, "game_id": game_id, "join_token": token})
    return templates.TemplateResponse("join.html", ctx)


@app.post("/game/{game_id}/join")
async def join_game(request: Request, game_id: str, join_token: str = Form(...)):
    black_token, err = gm.join_web_game(game_id, join_token)
    if err:
        return RedirectResponse(
            url=f"/game/{game_id}/join?token={join_token}&error={err}",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/game/{game_id}?player={black_token}",
        status_code=303,
    )


@app.post("/game/{game_id}/resign")
async def resign_game(
    request: Request,
    game_id: str,
    player_token: str = Form(...),
):
    result = gm.resign_web_game(game_id, player_token)
    if result["success"]:
        return RedirectResponse(
            url=f"/game/{game_id}?player={player_token}&msg=You+gave+up",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/game/{game_id}?player={player_token}&error={result['error']}",
        status_code=303,
    )


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request, token: str = ""):
    admin_token = os.environ.get("ADMIN_TOKEN")
    if not admin_token or token != admin_token:
        return HTMLResponse("Not Found", status_code=404)

    games = gm.list_games()
    ctx = _common_context(request)
    ctx.update({"request": request, "games": games})
    return templates.TemplateResponse("admin.html", ctx)


@app.post("/game/{game_id}/move")
async def make_move(
    request: Request,
    game_id: str,
    player_token: str = Form(...),
    move: str = Form(...),
):
    result = gm.make_web_move(game_id, player_token, move)
    if result["success"]:
        return RedirectResponse(
            url=f"/game/{game_id}?player={player_token}",
            status_code=303,
        )
    return RedirectResponse(
        url=f"/game/{game_id}?player={player_token}&error={result['error']}",
        status_code=303,
    )


# ==================== Battleship ====================

BS_COLS = list(battleship.COLS)


def _bs_flash(path: str, **params) -> str:
    return f"{path}?{urlencode(params)}"


def _bs_my_board(player_state: dict) -> list:
    ships = battleship.fleet_cells(player_state.get("fleet", []))
    shots = player_state.get("shots_received", {})
    grid = []
    for r in range(battleship.BOARD_SIZE):
        row = []
        for c in range(battleship.BOARD_SIZE):
            cell = battleship.rc_to_cell(r, c)
            if cell in shots:
                cls = "hit" if shots[cell] == "hit" else "miss"
            elif cell in ships:
                cls = "ship"
            else:
                cls = "water"
            row.append({"cell": cell, "cls": cls})
        grid.append(row)
    return grid


def _bs_enemy_board(player_state: dict, sunk_cells: set) -> list:
    shots = player_state.get("shots_made", {})
    grid = []
    for r in range(battleship.BOARD_SIZE):
        row = []
        for c in range(battleship.BOARD_SIZE):
            cell = battleship.rc_to_cell(r, c)
            cls = shots.get(cell, "unknown")
            if cls == "hit" and cell in sunk_cells:
                cls = "sunk"
            row.append({"cell": cell, "cls": cls})
        grid.append(row)
    return grid


def _bs_sunk_cells(events: list) -> set:
    sunk = set()
    for ev in events:
        if ev["event_type"] == "shot" and ev["data"].get("sunk"):
            sunk.update(ev["data"]["sunk"])
    return sunk


def _bs_fleet_remaining(fleet: list) -> list:
    remaining = list(battleship.FLEET)
    for ship in fleet:
        if len(ship) in remaining:
            remaining.remove(len(ship))
    return remaining


@app.get("/battleship", response_class=HTMLResponse)
async def battleship_index(request: Request):
    ctx = _common_context(request)
    ctx.update({"request": request})
    return templates.TemplateResponse("battleship_index.html", ctx)


@app.post("/battleship/create")
async def battleship_create(request: Request):
    game_id, player_token, _ = bsm.create_battleship_game()
    return RedirectResponse(
        url=f"/battleship/game/{game_id}?player={player_token}",
        status_code=303,
    )


@app.get("/battleship/game/{game_id}", response_class=HTMLResponse)
async def battleship_game_page(request: Request, game_id: str, player: str | None = None):
    game = bsm.get_battleship_game(game_id)
    if not game:
        ctx = _common_context(request)
        ctx.update({"request": request, "error": "Game not found or expired."})
        return templates.TemplateResponse("battleship_game.html", ctx, status_code=404)

    msg = request.query_params.get("msg")
    error = request.query_params.get("error")

    player_obj = bsm.get_player(player) if player else None
    my_side = None
    my_state = {}
    my_ready = False
    if player_obj and player_obj["game_id"] == game_id:
        my_side = player_obj["side"]
        my_state = player_obj["state"]
        my_ready = bool(player_obj["ready"])

    is_my_turn = game["status"] == "playing" and game["turn_side"] == my_side

    base_url = str(request.base_url).rstrip("/")
    spectator_link = f"{base_url}/battleship/game/{game_id}"

    share_link = None
    is_creator = False
    if game["status"] == "waiting":
        join_token_row = bsm.get_unused_join_token(game_id)
        if join_token_row:
            share_link = f"{base_url}/battleship/game/{game_id}/join?token={join_token_row}"
            if my_side == bsm.first_side:
                is_creator = True

    events = bsm.get_events(game_id)
    sunk_cells = _bs_sunk_cells(events)

    board_my = _bs_my_board(my_state) if my_side else None
    board_enemy = _bs_enemy_board(my_state, sunk_cells) if my_side else None
    fleet_remaining = _bs_fleet_remaining(my_state.get("fleet", [])) if my_side else []

    shot_log = [
        ev["data"] for ev in events if ev["event_type"] == "shot"
    ]

    opp_ready = False
    if my_side:
        opp = next((p for p in game["players"] if p["side"] != my_side), None)
        opp_ready = bool(opp["ready"]) if opp else False

    ctx = _common_context(request)
    ctx.update({
        "request": request,
        "game_id": game_id,
        "game_status": game["status"],
        "my_side": my_side,
        "my_ready": my_ready,
        "opp_ready": opp_ready,
        "is_my_turn": is_my_turn,
        "player_token": player,
        "share_link": share_link,
        "is_creator": is_creator,
        "winner": game["winner"],
        "result_reason": game["result_reason"],
        "time_left": _time_left(game["expires_at"]),
        "spectator_link": spectator_link,
        "board_my": board_my,
        "board_enemy": board_enemy,
        "fleet_remaining": fleet_remaining,
        "shot_log": shot_log,
        "cols": BS_COLS,
        "rows": list(range(1, 11)),
        "msg": msg,
        "error": error,
    })
    return templates.TemplateResponse("battleship_game.html", ctx)


@app.get("/battleship/game/{game_id}/join", response_class=HTMLResponse)
async def battleship_join_page(request: Request, game_id: str, token: str):
    _, err = bsm.validate_join_token(token)
    ctx = _common_context(request)
    if err:
        ctx.update({"request": request, "error": err})
        return templates.TemplateResponse("battleship_join.html", ctx)
    ctx.update({"request": request, "game_id": game_id, "join_token": token})
    return templates.TemplateResponse("battleship_join.html", ctx)


@app.post("/battleship/game/{game_id}/join")
async def battleship_join(request: Request, game_id: str, join_token: str = Form(...)):
    token, err = bsm.join_session(game_id, join_token)
    if err:
        return RedirectResponse(
            url=_bs_flash(f"/battleship/game/{game_id}/join", token=join_token, error=err),
            status_code=303,
        )
    return RedirectResponse(
        url=f"/battleship/game/{game_id}?player={token}",
        status_code=303,
    )


@app.post("/battleship/game/{game_id}/lock")
async def battleship_lock(
    request: Request,
    game_id: str,
    player_token: str = Form(...),
    fleet: str = Form(...),
):
    try:
        ships = json.loads(fleet)
    except ValueError:
        return RedirectResponse(
            url=_bs_flash(f"/battleship/game/{game_id}", player=player_token, error="Invalid fleet"),
            status_code=303,
        )

    result = bsm.submit_fleet(game_id, player_token, ships)
    if result["success"]:
        return RedirectResponse(
            url=_bs_flash(f"/battleship/game/{game_id}", player=player_token, msg="fleet_locked"),
            status_code=303,
        )
    return RedirectResponse(
        url=_bs_flash(f"/battleship/game/{game_id}", player=player_token, error=result["error"]),
        status_code=303,
    )


@app.post("/battleship/game/{game_id}/shoot")
async def battleship_shoot(
    request: Request,
    game_id: str,
    player_token: str = Form(...),
    cell: str = Form(...),
):
    result = bsm.make_shot(game_id, player_token, cell)
    if result["success"]:
        if result.get("ships_left") == 0:
            msg = "shot_win"
        else:
            msg = f"shot_{result['result']}"
        return RedirectResponse(
            url=_bs_flash(f"/battleship/game/{game_id}", player=player_token, msg=msg),
            status_code=303,
        )
    return RedirectResponse(
        url=_bs_flash(f"/battleship/game/{game_id}", player=player_token, error=result["error"]),
        status_code=303,
    )


@app.post("/battleship/game/{game_id}/resign")
async def battleship_resign(
    request: Request,
    game_id: str,
    player_token: str = Form(...),
):
    result = bsm.resign(game_id, player_token)
    if result["success"]:
        return RedirectResponse(
            url=_bs_flash(f"/battleship/game/{game_id}", player=player_token, msg="gave_up"),
            status_code=303,
        )
    return RedirectResponse(
        url=_bs_flash(f"/battleship/game/{game_id}", player=player_token, error=result["error"]),
        status_code=303,
    )
