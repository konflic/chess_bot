import asyncio
import datetime
import chess
import chess.svg
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from core.game_manager import ChessGameManager

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

HERE = os.path.dirname(__file__)

gm = ChessGameManager()


COPY_ICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" '
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
    'stroke-linejoin="round">'
    '<rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>'
    '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>'
)


def _common_context(request: Request) -> dict:
    lang = _get_lang(request)
    return {
        "lang": lang,
        "_": lambda key, **kw: _translate(lang, key, **kw),
        "copyIcon": COPY_ICON_SVG,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()

app = FastAPI(title="CheZZ Web", lifespan=lifespan)
templates = Jinja2Templates(directory=os.path.join(HERE, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")


async def _cleanup_loop():
    while True:
        await asyncio.sleep(300)
        deleted = gm.cleanup_expired_web_games()
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

    expires = datetime.datetime.fromisoformat(web_game["expires_at"])
    remaining = expires - datetime.datetime.utcnow()
    if remaining.total_seconds() > 0:
        hours = int(remaining.total_seconds() // 3600)
        minutes = int((remaining.total_seconds() % 3600) // 60)
        time_left = f"{hours}h {minutes:02d}min"
    else:
        time_left = "Expired"

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
        join_token_row = _get_join_token(game_id)
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


def _get_join_token(game_id: str) -> str | None:
    import sqlite3
    from configuration import GAMES_DB
    conn = sqlite3.connect(GAMES_DB)
    c = conn.cursor()
    c.execute(
        "SELECT join_token FROM web_join_tokens WHERE game_id = ? AND used = 0 LIMIT 1",
        (game_id,),
    )
    row = c.fetchone()
    conn.close()
    return row[0] if row else None


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

    games = gm.list_web_games()
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
