import asyncio
import datetime
import chess
import chess.svg
import os

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from core.game_manager import ChessGameManager

HERE = os.path.dirname(__file__)

app = FastAPI(title="CheZZ Web")
templates = Jinja2Templates(directory=os.path.join(HERE, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")

gm = ChessGameManager()


@app.on_event("startup")
async def startup():
    asyncio.create_task(_cleanup_loop())


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
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/games/create")
async def create_game(request: Request):
    game_id, white_token, join_token = gm.create_web_game()
    return RedirectResponse(
        url=f"/game/{game_id}?player={white_token}",
        status_code=303,
    )


@app.get("/game/{game_id}", response_class=HTMLResponse)
async def game_page(request: Request, game_id: str, player: str | None = None):
    web_game = gm.get_web_game(game_id)
    if not web_game:
        return templates.TemplateResponse(
            "game.html",
            {"request": request, "error": "Game not found or expired."},
            status_code=404,
        )

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
    moves = gm.get_web_moves(game_id)
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

    return templates.TemplateResponse("game.html", {
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
        "time_left": time_left,
        "spectator_link": spectator_link,
        "msg": msg,
        "error": error,
    })


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
    if err:
        return templates.TemplateResponse(
            "join.html",
            {"request": request, "error": err},
        )
    return templates.TemplateResponse("join.html", {
        "request": request,
        "game_id": game_id,
        "join_token": token,
    })


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
