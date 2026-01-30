#!/usr/bin/env python3

import sqlite3
import random
import string
import chess
import chess.svg
from telegram import Update, BotCommand, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import re
import os
import cairosvg
import time

from configuration import BOT_NAME, GAMES_DB, language_manager
import datetime


class ChessGameManager:
    def __init__(self, db_path=GAMES_DB):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize the database with necessary tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create games table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT UNIQUE NOT NULL,
                player1_id INTEGER,
                player2_id INTEGER,
                fen TEXT DEFAULT 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1',
                current_turn INTEGER,  -- player id whose turn it is
                status TEXT DEFAULT 'waiting',  -- waiting, playing, finished
                invite_link TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Create moves table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS moves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT,
                move_san TEXT,
                player_id INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (game_id) REFERENCES games (game_id)
            )
        """
        )

        # Create ping_history table to store ping timestamps
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ping_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER UNIQUE,
                last_ping_time TIMESTAMP
            )
        """
        )

        # Create active_games table to track which game is active for each user
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS active_games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER UNIQUE,
                active_game_id TEXT,
                FOREIGN KEY (active_game_id) REFERENCES games (game_id)
            )
        """
        )

        conn.commit()
        conn.close()

    def generate_invite_link(self):
        """Generate a unique invite link for a game."""
        return "".join(random.choices(string.ascii_letters + string.digits, k=12))

    def create_game(self, player1_id):
        """Create a new game and return the game ID and invite link."""
        game_id = "".join(random.choices(string.ascii_letters + string.digits, k=10))
        invite_link = self.generate_invite_link()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO games (game_id, player1_id, current_turn, invite_link)
                VALUES (?, ?, ?, ?)
            """,
                (game_id, player1_id, player1_id, invite_link),
            )

            conn.commit()
            conn.close()

            return game_id, invite_link
        except sqlite3.IntegrityError:
            # If there's a collision, try again with a new ID
            return self.create_game(player1_id)

    def join_game(self, invite_link, player2_id):
        """Join a game using an invite link."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT game_id, player1_id FROM games
            WHERE invite_link = ? AND player2_id IS NULL AND status = 'waiting'
        """,
            (invite_link,),
        )

        result = cursor.fetchone()
        if result:
            game_id, player1_id = result

            # Update the game to add player2 and start the game
            cursor.execute(
                """
                UPDATE games
                SET player2_id = ?, status = 'playing'
                WHERE game_id = ?
            """,
                (player2_id, game_id),
            )

            conn.commit()
            conn.close()

            return game_id, player1_id
        else:
            conn.close()
            return None, None

    def get_game(self, game_id):
        """Get game information by game ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT game_id, player1_id, player2_id, fen, current_turn, status
            FROM games WHERE game_id = ?
        """,
            (game_id,),
        )

        result = cursor.fetchone()
        conn.close()

        if result:
            return {
                "game_id": result[0],
                "player1_id": result[1],
                "player2_id": result[2],
                "fen": result[3],
                "current_turn": result[4],
                "status": result[5],
            }
        return None

    def make_move(self, game_id, move_san, player_id):
        """Make a move in the game."""
        game = self.get_game(game_id)
        if not game:
            return {"success": False, "error": "Game not found"}

        if game["current_turn"] != player_id:
            return {"success": False, "error": "Not your turn"}

        # Load the current position
        board = chess.Board(game["fen"])

        # Try to make the move
        try:
            move = board.parse_san(move_san)
            if board.is_legal(move):
                board.push(move)

                # Check game status
                if board.is_checkmate():
                    game_status = "finished"
                    winner = player_id
                elif (
                    board.is_stalemate()
                    or board.is_insufficient_material()
                    or board.can_claim_draw()
                ):
                    game_status = "finished"
                    winner = "draw"
                else:
                    # Switch turns
                    next_player = (
                        game["player2_id"]
                        if player_id == game["player1_id"]
                        else game["player1_id"]
                    )
                    game_status = "playing"
                    winner = None

                # Update the game
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()

                cursor.execute(
                    """
                    UPDATE games
                    SET fen = ?, current_turn = ?, status = ?
                    WHERE game_id = ?
                """,
                    (
                        board.fen(),
                        (
                            next_player
                            if game_status == "playing"
                            else game["current_turn"]
                        ),
                        game_status,
                        game_id,
                    ),
                )

                # Save the move
                cursor.execute(
                    """
                    INSERT INTO moves (game_id, move_san, player_id)
                    VALUES (?, ?, ?)
                """,
                    (game_id, move_san, player_id),
                )

                conn.commit()
                conn.close()

                return {
                    "success": True,
                    "new_fen": board.fen(),
                    "next_turn": next_player if game_status == "playing" else None,
                    "checkmate": board.is_checkmate(),
                    "stalemate": board.is_stalemate(),
                    "insufficient_material": board.is_insufficient_material(),
                    "winner": winner,
                    "status": game_status,
                }
            else:
                return {"success": False, "error": "Illegal move"}
        except ValueError:
            return {"success": False, "error": "Invalid move notation"}

    def delete_game(self, game_id):
        """Delete a finished game from the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM games WHERE game_id = ?", (game_id,))
        cursor.execute("DELETE FROM moves WHERE game_id = ?", (game_id,))

        conn.commit()
        conn.close()


class ChessBot:
    def __init__(self, token_file="TOKEN"):
        # Read the bot token
        with open(token_file, "r") as f:
            token = f.read().strip()

        self.application = Application.builder().token(token).build()
        self.game_manager = ChessGameManager()
        self.setup_handlers()
        self.setup_commands()

        # Dictionary to store the last ping time for each user
        self.last_ping = {}  # {user_id: datetime}

        # Dictionary to store active game for each user
        self.active_games = {}  # {user_id: game_id}

        # Load ping history and active games from database
        self.load_ping_history()
        self.load_active_games()

        # Create tmp directory if it doesn't exist
        if not os.path.exists("tmp"):
            os.makedirs("tmp")

    def load_ping_history(self):
        """Load ping history from the database."""
        conn = sqlite3.connect(self.game_manager.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT player_id, last_ping_time FROM ping_history")
        results = cursor.fetchall()

        for player_id, last_ping_time in results:
            # Convert string timestamp to datetime object
            self.last_ping[player_id] = datetime.datetime.fromisoformat(last_ping_time)

        conn.close()

    def load_active_games(self):
        """Load active games from the database."""
        conn = sqlite3.connect(self.game_manager.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT player_id, active_game_id FROM active_games")
        results = cursor.fetchall()

        for player_id, active_game_id in results:
            self.active_games[player_id] = active_game_id

        conn.close()

    def set_active_game(self, player_id, game_id):
        """Set the active game for a player."""
        # Update in memory
        self.active_games[player_id] = game_id

        # Update in database
        conn = sqlite3.connect(self.game_manager.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            REPLACE INTO active_games (player_id, active_game_id)
            VALUES (?, ?)
            """,
            (player_id, game_id),
        )

        conn.commit()
        conn.close()

    def get_active_game(self, player_id):
        """Get the active game for a player."""
        # Check in memory first
        if player_id in self.active_games:
            return self.active_games[player_id]

        # If not in memory, check database
        conn = sqlite3.connect(self.game_manager.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT active_game_id FROM active_games WHERE player_id = ?", (player_id,)
        )

        result = cursor.fetchone()
        conn.close()

        if result:
            # Update memory cache
            self.active_games[player_id] = result[0]
            return result[0]

        return None

    def setup_handlers(self):
        """Set up command handlers."""
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("newgame", self.new_game))
        self.application.add_handler(CommandHandler("current_game", self.current_game))
        self.application.add_handler(
            CommandHandler("active_games", self.active_games_command)
        )
        self.application.add_handler(
            CommandHandler("set_active", self.set_active_command)
        )
        self.application.add_handler(CommandHandler("surrender", self.surrender_game))
        self.application.add_handler(
            CommandHandler("confirm_surrender", self.confirm_surrender)
        )
        self.application.add_handler(CommandHandler("cancel", self.cancel_surrender))
        self.application.add_handler(CommandHandler("ping", self.ping_opponent))
        self.application.add_handler(CommandHandler("board", self.show_board))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_move)
        )

    async def setup_commands(self):
        """Set up bot commands menu in Telegram interface."""
        commands = [
            BotCommand("start", "Show welcome message and instructions"),
            BotCommand("newgame", "Start a new chess game"),
            BotCommand("current_game", "Show your current active game info"),
            BotCommand("active_games", "Show all your active games"),
            BotCommand("board", "Show the current board state"),
            BotCommand("surrender", "Surrender current game (forfeit)"),
            BotCommand("ping", "Notify your opponent it's their turn"),
        ]

        await self.application.bot.set_my_commands(commands)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /start command."""
        user = update.effective_user

        # Detect user language from Telegram
        user_language = update.effective_user.language_code

        # Check if there are arguments (deep link)
        if context.args and len(context.args) > 0:
            payload = context.args[0]  # e.g., "join_GApw0W43gKLS"

            # Handle join deep links
            if payload.startswith("join_"):
                invite_link = payload[5:]  # Remove "join_" prefix

                # Check if user is already in a game
                conn = sqlite3.connect(self.game_manager.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT game_id FROM games
                    WHERE (player1_id = ? OR player2_id = ?) AND status = 'playing'
                """,
                    (user.id, user.id),
                )
                active_game = cursor.fetchone()
                conn.close()

                if active_game:
                    await update.message.reply_text(
                        f"⚠️ {language_manager.get_message('already_in_game', user.id, user_language)}\n"
                        f"{language_manager.get_message('game_id', user.id)}: `{active_game[0]}`\n"
                        f"{language_manager.get_message('use_current_game', user.id)}\n"
                        f"{language_manager.get_message('or_leave', user.id)}",
                        parse_mode="HTML",
                    )
                    return

                # Try to join the game
                game_id, opponent_id = self.game_manager.join_game(invite_link, user.id)

                if game_id:
                    # Set this as the active game for the player
                    self.set_active_game(user.id, game_id)
                    # Determine if user is white or black
                    game_info = self.game_manager.get_game(game_id)
                    is_white = game_info["player1_id"] == user.id
                    color = (
                        language_manager.get_message("white", user.id, user_language)
                        if is_white
                        else language_manager.get_message(
                            "black", user.id, user_language
                        )
                    )

                    with open("start.png", "rb") as f:
                        await update.message.reply_photo(
                            photo=f,
                            caption=(
                                f"✅ {language_manager.get_message('joined_success', user.id, user_language)}\n\n"
                                f"{language_manager.get_message('game_id', user.id)}: `{game_id}`\n"
                                f"{language_manager.get_message('you_are', user.id)} {color}\n\n"
                                + (
                                    language_manager.get_message("your_turn", user.id)
                                    if is_white
                                    else language_manager.get_message(
                                        "waiting_opponent", user.id
                                    )
                                )
                            ),
                            parse_mode="HTML",
                        )

                    # Notify the other player
                    if opponent_id:
                        # Get opponent's language preference
                        opponent_color = (
                            language_manager.get_message("black", opponent_id)
                            if is_white
                            else language_manager.get_message("white", opponent_id)
                        )
                        try:
                            with open("start.png", "rb") as f:
                                await context.bot.send_photo(
                                    chat_id=opponent_id,
                                    photo=f,
                                    caption=(
                                        f"✅ {user.username} {language_manager.get_message('has_joined', opponent_id)}\n\n"
                                        f"{language_manager.get_message('game_id', opponent_id)}: `{game_id}`\n"
                                        f"{language_manager.get_message('you_are', opponent_id)} {opponent_color}\n\n"
                                        + (
                                            language_manager.get_message(
                                                "your_turn", opponent_id
                                            )
                                            if not is_white
                                            else language_manager.get_message(
                                                "waiting_opponent", opponent_id
                                            )
                                        )
                                    ),
                                    parse_mode="HTML",
                                )
                        except Exception:
                            pass
                else:
                    await update.message.reply_text(
                        f"❌ {language_manager.get_message('invalid_invite', user.id, user_language)}\n\n"
                        f"{language_manager.get_message('invalid_reasons', user.id)}\n"
                        f"{language_manager.get_message('game_has_players', user.id)}\n"
                        f"{language_manager.get_message('game_not_exist', user.id)}\n"
                        f"{language_manager.get_message('link_expired', user.id)}\n\n"
                        f"{language_manager.get_message('create_own_game', user.id)}"
                    )
                return

        # Regular /start without parameters
        welcome_message = (
            f"<b>{language_manager.get_message('welcome_title', user.id, user_language)}</b>\n\n"
            f"<b>{language_manager.get_message('welcome_commands', user.id)}</b>\n"
            f"{language_manager.get_message('welcome_newgame', user.id)}\n"
            f"{language_manager.get_message('welcome_current_game', user.id)}\n"
            f"{language_manager.get_message('welcome_leave', user.id)}\n\n"
            f"<b>{language_manager.get_message('welcome_how_to_play', user.id)}</b>\n"
            f"{language_manager.get_message('welcome_move_format', user.id)}"
        )

        # Create a keyboard with common commands
        keyboard = [["/newgame", "/current_game"], ["/active_games", "/surrender"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

        await update.message.reply_text(
            welcome_message, parse_mode="HTML", reply_markup=reply_markup
        )

    async def new_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start a new game."""
        user = update.effective_user
        player_id = user.id
        user_language = user.language_code

        # Create a new game
        game_id, invite_link = self.game_manager.create_game(player_id)

        # Set this as the active game for the player
        self.set_active_game(player_id, game_id)

        deep_link = f"https://t.me/{BOT_NAME}?start=join_{invite_link}"

        invite_message = (
            f"<b>{language_manager.get_message('new_game_created', user.id, user_language)}</b>\n\n"
            f"<b>{language_manager.get_message('game_id', user.id)}:</b> <code>{game_id}</code>\n"
            f"<b>{language_manager.get_message('invite_code', user.id)}:</b> <code>{invite_link}</code>\n\n"
            f"<b>{language_manager.get_message('share_link', user.id)}</b>\n{deep_link}"
        )
        await update.message.reply_text(invite_message, parse_mode="HTML")

    async def join_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Join a game using an invite link."""
        user = update.effective_user
        player_id = user.id
        user_language = user.language_code

        # Check if user provided an invite link
        if len(context.args) != 1:
            await update.message.reply_text(
                language_manager.get_message("invalid_invite", user.id, user_language)
            )
            return

        invite_link = context.args[0]

        # Check if user is already in a game
        conn = sqlite3.connect(self.game_manager.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT game_id FROM games
            WHERE (player1_id = ? OR player2_id = ?) AND status = 'playing'
        """,
            (player_id, player_id),
        )
        active_game = cursor.fetchone()
        conn.close()

        if active_game:
            await update.message.reply_text(
                f"{language_manager.get_message('already_in_game', user.id, user_language)} ({active_game[0]})!"
            )
            return

        # Try to join the game
        game_id, opponent_id = self.game_manager.join_game(invite_link, player_id)

        if game_id:
            # Set this as the active game for the player
            self.set_active_game(player_id, game_id)
            # Get the initial board state
            board = chess.Board()
            svg_file = self.render_board(board)

            with open(svg_file, "rb") as f:
                await update.message.reply_photo(
                    photo=f,
                    caption=f"{language_manager.get_message('joined_success', user.id, user_language)} {game_id}!\n\n{language_manager.get_message('white', user.id)} ({update.effective_user.username}) {language_manager.get_message('your_turn', user.id)}",
                    parse_mode="HTML",
                )
            # Clean up temp file
            os.unlink(svg_file)

            # Notify the other player
            try:
                opponent_svg_file = self.render_board(board)
                with open(opponent_svg_file, "rb") as f:
                    await context.bot.send_photo(
                        chat_id=opponent_id,
                        photo=f,
                        caption=f"{language_manager.get_message('player_joined', opponent_id)} {update.effective_user.username}!\n{language_manager.get_message('game_id', opponent_id)}: {game_id}",
                    )
                os.unlink(opponent_svg_file)
            except Exception:
                pass  # Ignore if unable to send message
        else:
            await update.message.reply_text(
                language_manager.get_message("invalid_invite", user.id, user_language)
            )

    async def handle_move(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle chess moves."""
        user = update.effective_user
        player_id = user.id
        user_language = user.language_code
        move_text = update.message.text.strip().lower()

        if not self.is_valid_move_format(move_text):
            return  # Don't respond to non-move messages

        # Get the active game ID for this user
        active_game_id = self.get_active_game(player_id)

        # If no active game is set, check if the user has any games
        if not active_game_id:
            conn = sqlite3.connect(self.game_manager.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT g.game_id
                FROM games g
                WHERE (g.player1_id = ? OR g.player2_id = ?) AND g.status = 'playing'
                ORDER BY g.created_at DESC
                LIMIT 1
            """,
                (player_id, player_id),
            )

            result = cursor.fetchone()
            conn.close()

            if result:
                # Set the first game as active
                active_game_id = result[0]
                self.set_active_game(player_id, active_game_id)
            else:
                await update.message.reply_text(
                    language_manager.get_message(
                        "not_in_active_game", user.id, user_language
                    )
                )
                return

        # Verify the game exists and the user is a participant
        conn = sqlite3.connect(self.game_manager.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT game_id FROM games
            WHERE game_id = ? AND (player1_id = ? OR player2_id = ?) AND status = 'playing'
        """,
            (active_game_id, player_id, player_id),
        )
        result = cursor.fetchone()
        conn.close()

        if not result:
            await update.message.reply_text(
                language_manager.get_message(
                    "not_in_active_game", user.id, user_language
                )
            )
            return

        game_id = active_game_id

        # Make the move
        result = self.game_manager.make_move(game_id, move_text, player_id)

        if result["success"]:
            # Get updated game info
            game_info = self.game_manager.get_game(game_id)

            # Create the board
            board = chess.Board(result["new_fen"])

            # Get PNG file path
            png_file = self.render_board(board, game_id)

            # Determine who's turn it is now
            current_player = (
                language_manager.get_message("white", user.id)
                if game_info["current_turn"] == game_info["player1_id"]
                else language_manager.get_message("black", user.id)
            )

            # Check if game is finished
            if result["status"] == "finished":
                # Get opponent ID
                opponent_id = (
                    game_info["player2_id"]
                    if player_id == game_info["player1_id"]
                    else game_info["player1_id"]
                )

                if result["winner"] == "draw":
                    # DRAW - notify both players
                    player_caption = f"🏁 {language_manager.get_message('game_draw', user.id, user_language)}"
                    opponent_caption = (
                        f"🏁 {language_manager.get_message('game_draw', opponent_id)}"
                    )

                    # Send to player who made the move
                    with open(png_file, "rb") as f:
                        await update.message.reply_photo(
                            photo=f, caption=player_caption, parse_mode="HTML"
                        )

                    # Clean up temp file
                    os.unlink(png_file)

                    # Send to opponent
                    if opponent_id:
                        try:
                            opponent_png_file = self.render_board(board, game_id)
                            with open(opponent_png_file, "rb") as f:
                                await context.bot.send_photo(
                                    chat_id=opponent_id,
                                    photo=f,
                                    caption=opponent_caption,
                                    parse_mode="HTML",
                                )
                            os.unlink(opponent_png_file)
                        except Exception:
                            pass  # Ignore if unable to send message

                else:
                    # CHECKMATE - one player wins, one loses
                    is_winner = result["winner"] == player_id

                    if is_winner:
                        # Current player is the WINNER
                        player_caption = f"🏆 {language_manager.get_message('checkmate_win', user.id, user_language)}"
                        opponent_caption = f"💀 {language_manager.get_message('checkmate_lose', opponent_id)}"
                    else:
                        # Current player is the LOSER
                        player_caption = f"💀 {language_manager.get_message('checkmate_lose', user.id, user_language)}"
                        opponent_caption = f"🏆 {language_manager.get_message('checkmate_win', opponent_id)}"

                    # Send to player who made the move
                    with open(png_file, "rb") as f:
                        await update.message.reply_photo(
                            photo=f, caption=player_caption, parse_mode="HTML"
                        )

                    # Clean up temp file
                    os.unlink(png_file)

                    # Send to opponent
                    if opponent_id:
                        try:
                            opponent_png_file = self.render_board(board, game_id)
                            with open(opponent_png_file, "rb") as f:
                                await context.bot.send_photo(
                                    chat_id=opponent_id,
                                    photo=f,
                                    caption=opponent_caption,
                                    parse_mode="HTML",
                                )
                            os.unlink(opponent_png_file)
                        except Exception:
                            pass  # Ignore if unable to send message

                # Delete the finished game
                self.game_manager.delete_game(game_id)

            else:
                # Game continues
                caption = f"{language_manager.get_message('move', user.id)}: {move_text}\n{language_manager.get_message('current_turn', user.id)}: {current_player}"

                # Send to player who made the move
                with open(png_file, "rb") as f:
                    await update.message.reply_photo(
                        photo=f, caption=caption, parse_mode="HTML"
                    )

                # Clean up temp file
                os.unlink(png_file)

                # Notify the other player
                other_player_id = (
                    game_info["player2_id"]
                    if player_id == game_info["player1_id"]
                    else game_info["player1_id"]
                )
                try:
                    # Create another PNG for the opponent
                    opponent_png_file = self.render_board(board, game_id)
                    opponent_caption = f"{language_manager.get_message('opponent_played', other_player_id)} {update.effective_user.username} {move_text}\n\n{language_manager.get_message('your_turn_exclamation', other_player_id)}"

                    with open(opponent_png_file, "rb") as f:
                        await context.bot.send_photo(
                            chat_id=other_player_id,
                            photo=f,
                            caption=opponent_caption,
                            parse_mode="HTML",
                        )

                    # Clean up temp file
                    os.unlink(opponent_png_file)

                except Exception:
                    pass  # Ignore if unable to send message
        else:
            await update.message.reply_text(
                f"{language_manager.get_message('invalid_move', user.id, user_language)} {result['error']}"
            )

    def is_valid_move_format(self, move_text):
        """Check if the move format is potentially valid."""
        # Matches standard algebraic notation like e4, Nf3, O-O, etc.
        pattern = r"^([a-h][1-8][a-h][1-8]|[a-h][1-8]|O-O(-O)?|N[a-h][1-8]?|B[a-h][1-8]?|R[a-h][1-8]?|Q[a-h][1-8]?|K[a-h][1-8]?)$"
        return bool(re.match(pattern, move_text.lower()))

    def render_board(self, board, game_id=None):
        """Render the chess board as a PNG image and return file path."""
        timestamp = int(time.time())
        random_suffix = random.randint(1000, 9999)
        filename = f"board_{timestamp}_{random_suffix}.png"
        tmp_dir = "tmp"

        print(filename)

        if game_id:
            # Create game-specific subdirectory
            game_dir = os.path.join(tmp_dir, game_id)
            if not os.path.exists(game_dir):
                os.makedirs(game_dir)
            filepath = os.path.join(game_dir, filename)
        else:
            filepath = os.path.join(tmp_dir, filename)

        # Generate SVG and convert to PNG
        svg_content = chess.svg.board(board=board, size=400, coordinates=True)
        png_bytes = cairosvg.svg2png(bytestring=svg_content.encode("utf-8"))

        # Save to file
        with open(filepath, "wb") as f:
            f.write(png_bytes)

        return filepath

    async def current_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's current active game information."""
        user = update.effective_user
        player_id = user.id
        user_language = user.language_code

        # Get the active game ID for this user
        active_game_id = self.get_active_game(player_id)

        # If no active game is set, check if the user has any games
        if not active_game_id:
            conn = sqlite3.connect(self.game_manager.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT g.game_id
                FROM games g
                WHERE (g.player1_id = ? OR g.player2_id = ?) AND g.status = 'playing'
                ORDER BY g.created_at DESC
                LIMIT 1
            """,
                (player_id, player_id),
            )

            result = cursor.fetchone()
            conn.close()

            if result:
                # Set the first game as active
                active_game_id = result[0]
                self.set_active_game(player_id, active_game_id)
            else:
                await update.message.reply_text(
                    language_manager.get_message(
                        "no_active_games", user.id, user_language
                    )
                )
                return

        # Get the active game details
        conn = sqlite3.connect(self.game_manager.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT g.game_id, g.player1_id, g.player2_id, g.created_at, g.current_turn, g.fen
            FROM games g
            WHERE g.game_id = ? AND (g.player1_id = ? OR g.player2_id = ?) AND g.status = 'playing'
        """,
            (active_game_id, player_id, player_id),
        )

        result = cursor.fetchone()
        conn.close()

        if not result:
            # This shouldn't happen, but just in case
            await update.message.reply_text(
                language_manager.get_message("no_active_games", user.id, user_language)
            )
            return

        game_id, player1_id, player2_id, created_at, current_turn, fen = result

        # Determine opponent ID and get opponent username
        opponent_id = player2_id if player_id == player1_id else player1_id

        # Since we don't store usernames in the database, we'll try to get the username from Telegram
        try:
            # Get the opponent user info
            opponent_user = await context.bot.get_chat(opponent_id)
            opponent_name = opponent_user.username or f"User {opponent_id}"
        except Exception:
            # If we can't get the user info from Telegram, just use the ID
            opponent_name = f"User {opponent_id}"

        # Determine whose turn it is
        is_your_turn = current_turn == player_id
        turn_message = (
            language_manager.get_message("your_turn", user.id)
            if is_your_turn
            else language_manager.get_message("waiting_opponent", user.id)
        )

        # Determine player color
        is_white = player1_id == player_id
        player_color = (
            language_manager.get_message("white", user.id)
            if is_white
            else language_manager.get_message("black", user.id)
        )

        # Format the response
        game_info_message = (
            f"<b>{language_manager.get_message('current_active_game', user.id, user_language)}</b>"
            f"\n{language_manager.get_message('game_id', user.id)}: {game_id}"
            f"\n{language_manager.get_message('opponent', user.id)}: {opponent_name}"
            f"\n{language_manager.get_message('started_at', user.id)}: {created_at}"
            f"\n{language_manager.get_message('you_are', user.id)}: {player_color}"
            f"\n{language_manager.get_message('current_turn', user.id)}: {turn_message}"
            f"\n\n{language_manager.get_message('board_command', user.id)}"
        )

        await update.message.reply_text(game_info_message, parse_mode="HTML")

    async def surrender_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ask for confirmation before surrendering the game."""
        user = update.effective_user
        player_id = user.id
        user_language = user.language_code

        # Get the active game ID for this user
        active_game_id = self.get_active_game(player_id)

        # If no active game is set, check if the user has any games
        if not active_game_id:
            conn = sqlite3.connect(self.game_manager.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT g.game_id
                FROM games g
                WHERE (g.player1_id = ? OR g.player2_id = ?) AND g.status = 'playing'
                ORDER BY g.created_at DESC
                LIMIT 1
            """,
                (player_id, player_id),
            )

            result = cursor.fetchone()
            conn.close()

            if result:
                # Set the first game as active
                active_game_id = result[0]
                self.set_active_game(player_id, active_game_id)
            else:
                await update.message.reply_text(
                    f"❌ {language_manager.get_message('no_active_game', user.id, user_language)}\n"
                    f"{language_manager.get_message('create_own_game', user.id)}",
                    parse_mode="HTML",
                )
                return

        # Verify the game exists
        conn = sqlite3.connect(self.game_manager.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT g.game_id
            FROM games g
            WHERE g.game_id = ? AND (g.player1_id = ? OR g.player2_id = ?) AND g.status = 'playing'
        """,
            (active_game_id, player_id, player_id),
        )

        result = cursor.fetchone()
        conn.close()

        if not result:
            await update.message.reply_text(
                f"❌ {language_manager.get_message('no_active_game', user.id, user_language)}\n"
                f"{language_manager.get_message('create_own_game', user.id)}",
                parse_mode="HTML",
            )
            return

        # Store the game_id in user_data for later use in confirm_surrender
        context.user_data["surrender_game_id"] = active_game_id

        # Ask for confirmation
        await update.message.reply_text(
            language_manager.get_message("confirm_surrender", user.id, user_language),
            parse_mode="HTML",
        )

    async def confirm_surrender(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Confirm surrender and end the game."""
        user = update.effective_user
        player_id = user.id
        user_language = user.language_code
        username = user.username or user.first_name

        # Check if there's a pending surrender confirmation
        if "surrender_game_id" not in context.user_data:
            await update.message.reply_text(
                f"❌ {language_manager.get_message('no_active_game', user.id, user_language)}",
                parse_mode="HTML",
            )
            return

        game_id = context.user_data["surrender_game_id"]

        # Find opponent
        conn = sqlite3.connect(self.game_manager.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT CASE
                WHEN g.player1_id = ? THEN g.player2_id
                ELSE g.player1_id
            END as opponent_id
            FROM games g
            WHERE g.game_id = ? AND status = 'playing'
        """,
            (player_id, game_id),
        )

        result = cursor.fetchone()

        if not result:
            await update.message.reply_text(
                f"❌ {language_manager.get_message('no_active_game', user.id, user_language)}",
                parse_mode="HTML",
            )
            conn.close()
            return

        opponent_id = result[0]

        # Delete the game
        self.game_manager.delete_game(game_id)

        # Clear the surrender confirmation from user_data
        del context.user_data["surrender_game_id"]

        # Notify the player who surrendered
        await update.message.reply_text(
            f"<b>{language_manager.get_message('game_ended', user.id, user_language)}</b>\n\n"
            f"{language_manager.get_message('left_game', user.id)} <code>{game_id}</code>.\n"
            f"{language_manager.get_message('opponent_wins', user.id)}\n\n"
            f"{language_manager.get_message('start_new_game', user.id)} <code>/newgame</code>",
            parse_mode="HTML",
        )

        # Notify the opponent
        if opponent_id:
            try:
                await context.bot.send_message(
                    chat_id=opponent_id,
                    text=f"<b>{language_manager.get_message('victory_forfeit', opponent_id)}</b>\n\n"
                    f"{language_manager.get_message('player_left', opponent_id)} <b>{username}</b> <code>{game_id}</code>.\n"
                    f"{language_manager.get_message('awarded_win', opponent_id)}\n\n"
                    f"{language_manager.get_message('start_new_game', opponent_id)} <code>/newgame</code>",
                    parse_mode="HTML",
                )
            except Exception as e:
                print(f"Note: Could not notify opponent {opponent_id}: {e}")

        conn.close()

    async def cancel_surrender(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Cancel the surrender confirmation."""
        user = update.effective_user
        user_language = user.language_code

        # Check if there's a pending surrender confirmation
        if "surrender_game_id" not in context.user_data:
            await update.message.reply_text(
                f"❌ {language_manager.get_message('no_active_game', user.id, user_language)}",
                parse_mode="HTML",
            )
            return

        # Clear the surrender confirmation from user_data
        del context.user_data["surrender_game_id"]

        # Notify the player
        await update.message.reply_text(
            language_manager.get_message("surrender_cancelled", user.id, user_language),
            parse_mode="HTML",
        )

    async def ping_opponent(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a reminder to the opponent that it's their turn."""
        user = update.effective_user
        player_id = user.id
        user_language = user.language_code

        # Get the active game ID for this user
        active_game_id = self.get_active_game(player_id)

        # If no active game is set, check if the user has any games
        if not active_game_id:
            conn = sqlite3.connect(self.game_manager.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT g.game_id
                FROM games g
                WHERE (g.player1_id = ? OR g.player2_id = ?) AND g.status = 'playing'
                ORDER BY g.created_at DESC
                LIMIT 1
            """,
                (player_id, player_id),
            )

            result = cursor.fetchone()
            conn.close()

            if result:
                # Set the first game as active
                active_game_id = result[0]
                self.set_active_game(player_id, active_game_id)
            else:
                await update.message.reply_text(
                    language_manager.get_message("ping_no_game", user.id, user_language)
                )
                return

        # Get the active game details
        conn = sqlite3.connect(self.game_manager.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT g.game_id, g.player1_id, g.player2_id, g.current_turn
            FROM games g
            WHERE g.game_id = ? AND (g.player1_id = ? OR g.player2_id = ?) AND g.status = 'playing'
        """,
            (active_game_id, player_id, player_id),
        )

        result = cursor.fetchone()
        conn.close()

        if not result:
            await update.message.reply_text(
                language_manager.get_message("ping_no_game", user.id, user_language)
            )
            return

        game_id, player1_id, player2_id, current_turn = result

        # Determine opponent ID
        opponent_id = player2_id if player_id == player1_id else player1_id

        # Check if it's the opponent's turn (not the user's turn)
        if current_turn == player_id:
            await update.message.reply_text(
                language_manager.get_message(
                    "ping_not_opponent_turn", user.id, user_language
                )
            )
            return

        # Check if the user has already sent a ping in the last 30 minutes
        now = datetime.datetime.now()
        if player_id in self.last_ping:
            time_since_last_ping = now - self.last_ping[player_id]
            if time_since_last_ping.total_seconds() < 1800:  # 30 minutes = 1800 seconds
                await update.message.reply_text(
                    language_manager.get_message(
                        "ping_cooldown", user.id, user_language
                    )
                )
                return

        # Update the last ping time in memory
        self.last_ping[player_id] = now

        # Update the last ping time in the database
        conn = sqlite3.connect(self.game_manager.db_path)
        cursor = conn.cursor()

        # Use REPLACE to handle both insert and update cases
        cursor.execute(
            """
            REPLACE INTO ping_history (player_id, last_ping_time)
            VALUES (?, ?)
        """,
            (player_id, now.isoformat()),
        )

        conn.commit()
        conn.close()

        # Send notification to the opponent
        try:
            # Get the user's username
            username = user.username or user.first_name

            await context.bot.send_message(
                chat_id=opponent_id,
                text=f"🔔 <b>{username}</b> {language_manager.get_message('ping_received', opponent_id)}",
                parse_mode="HTML",
            )

            # Confirm to the user that the ping was sent
            await update.message.reply_text(
                language_manager.get_message("ping_sent", user.id, user_language)
            )
        except Exception as e:
            print(f"Could not send ping to opponent {opponent_id}: {e}")
            # If we couldn't send the message, don't count this as a ping
            if player_id in self.last_ping:
                del self.last_ping[player_id]

                # Also remove from database
                conn = sqlite3.connect(self.game_manager.db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM ping_history WHERE player_id = ?", (player_id,)
                )
                conn.commit()
                conn.close()

    async def show_board(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show the current board state."""
        user = update.effective_user
        player_id = user.id
        user_language = user.language_code

        # Get the active game ID for this user
        active_game_id = self.get_active_game(player_id)

        # If no active game is set, check if the user has any games
        if not active_game_id:
            conn = sqlite3.connect(self.game_manager.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT g.game_id
                FROM games g
                WHERE (g.player1_id = ? OR g.player2_id = ?) AND g.status = 'playing'
                ORDER BY g.created_at DESC
                LIMIT 1
            """,
                (player_id, player_id),
            )

            result = cursor.fetchone()
            conn.close()

            if result:
                # Set the first game as active
                active_game_id = result[0]
                self.set_active_game(player_id, active_game_id)
            else:
                await update.message.reply_text(
                    language_manager.get_message(
                        "no_active_board", user.id, user_language
                    )
                )
                return

        # Get the active game details
        conn = sqlite3.connect(self.game_manager.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT g.game_id, g.fen
            FROM games g
            WHERE g.game_id = ? AND (g.player1_id = ? OR g.player2_id = ?) AND g.status = 'playing'
        """,
            (active_game_id, player_id, player_id),
        )

        result = cursor.fetchone()
        conn.close()

        if not result:
            await update.message.reply_text(
                language_manager.get_message("no_active_board", user.id, user_language)
            )
            return

        game_id, fen = result

        # Create the board
        board = chess.Board(fen)

        # Get PNG file path
        png_file = self.render_board(board, game_id)

        # Send the board image
        with open(png_file, "rb") as f:
            await update.message.reply_photo(
                photo=f,
                caption=f"{language_manager.get_message('current_active_game', user.id, user_language)}: {game_id}",
                parse_mode="HTML",
            )

        # Clean up temp file
        os.unlink(png_file)

    async def active_games_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Show all active games for the user."""
        user = update.effective_user
        player_id = user.id
        user_language = user.language_code

        # Find all active games for the user
        conn = sqlite3.connect(self.game_manager.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT g.game_id, g.player1_id, g.player2_id, g.current_turn, g.fen
            FROM games g
            WHERE (g.player1_id = ? OR g.player2_id = ?) AND g.status = 'playing'
            ORDER BY g.created_at DESC
        """,
            (player_id, player_id),
        )

        games = cursor.fetchall()
        conn.close()

        if not games:
            await update.message.reply_text(
                language_manager.get_message("no_active_games", user.id, user_language)
            )
            return

        # Get the current active game
        active_game_id = self.get_active_game(player_id)

        # If no active game is set but the user has games, set the first one as active
        if not active_game_id and games:
            active_game_id = games[0][0]
            self.set_active_game(player_id, active_game_id)

        # Build the response message
        response = f"<b>{language_manager.get_message('active_games', user.id, user_language)}</b>\n\n"

        for game_id, player1_id, player2_id, current_turn, fen in games:
            # Determine opponent ID
            opponent_id = player2_id if player_id == player1_id else player1_id

            # Get opponent username
            try:
                opponent_user = await context.bot.get_chat(opponent_id)
                opponent_name = opponent_user.username or f"User {opponent_id}"
            except Exception:
                opponent_name = f"User {opponent_id}"

            # Determine player color
            is_white = player1_id == player_id
            player_color = (
                language_manager.get_message("white", user.id)
                if is_white
                else language_manager.get_message("black", user.id)
            )

            # Determine whose turn it is
            is_your_turn = current_turn == player_id
            turn_message = (
                language_manager.get_message("your_turn", user.id)
                if is_your_turn
                else language_manager.get_message("waiting_opponent", user.id)
            )

            # Mark the active game
            active_marker = "➡️ " if game_id == active_game_id else ""

            # Format game details
            game_details = language_manager.get_message("game_details", user.id) % (
                game_id,
                opponent_name,
                player_color,
                turn_message,
            )

            response += f"{active_marker}{game_details}\n"
            response += f"/set_active {game_id} - {language_manager.get_message('set_active_game', user.id)}\n\n"

        await update.message.reply_text(response, parse_mode="HTML")

        # If there's an active game, show the board
        if active_game_id:
            # Find the game with the active_game_id
            for game in games:
                if game[0] == active_game_id:
                    # Create the board
                    board = chess.Board(game[4])  # fen is at index 4

                    # Get PNG file path
                    png_file = self.render_board(board, active_game_id)

                    # Send the board image
                    with open(png_file, "rb") as f:
                        await update.message.reply_photo(
                            photo=f,
                            caption=f"{language_manager.get_message('current_active_game', user.id, user_language)}: {active_game_id}",
                            parse_mode="HTML",
                        )

                    # Clean up temp file
                    os.unlink(png_file)
                    break

    async def set_active_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Set a game as the active game."""
        user = update.effective_user
        player_id = user.id
        user_language = user.language_code

        # Check if user provided a game ID
        if len(context.args) != 1:
            await update.message.reply_text(
                language_manager.get_message("no_active_games", user.id, user_language)
            )
            return

        game_id = context.args[0]

        # Check if the game exists and the user is a participant
        conn = sqlite3.connect(self.game_manager.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT g.fen
            FROM games g
            WHERE g.game_id = ? AND (g.player1_id = ? OR g.player2_id = ?) AND g.status = 'playing'
        """,
            (game_id, player_id, player_id),
        )

        result = cursor.fetchone()
        conn.close()

        if not result:
            await update.message.reply_text(
                language_manager.get_message("no_active_games", user.id, user_language)
            )
            return

        fen = result[0]

        # Set the game as active
        self.set_active_game(player_id, game_id)

        # Notify the user
        await update.message.reply_text(
            language_manager.get_message("game_set_active", user.id, user_language)
            % game_id,
            parse_mode="HTML",
        )

        # Show the board
        board = chess.Board(fen)
        png_file = self.render_board(board, game_id)

        with open(png_file, "rb") as f:
            await update.message.reply_photo(
                photo=f,
                caption=f"{language_manager.get_message('current_active_game', user.id, user_language)}: {game_id}",
                parse_mode="HTML",
            )

        # Clean up temp file
        os.unlink(png_file)

    def run(self):
        """Run the bot."""
        print("Starting chess bot...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)
