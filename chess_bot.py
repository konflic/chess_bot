#!/usr/bin/env python3

import sqlite3
import random
import string
import chess  # This imports the python-chess library (not our file)
import chess.svg
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
import re
import os

from configuration import BOT_NAME, GAMES_DB


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

    def setup_handlers(self):
        """Set up command handlers."""
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("newgame", self.new_game))
        self.application.add_handler(CommandHandler("join", self.join_game))
        self.application.add_handler(CommandHandler("current_game", self.current_game))
        self.application.add_handler(CommandHandler("leave", self.leave_game))
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_move)
        )

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /start command."""
        user = update.effective_user

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
                        f"⚠️ You're already in an active game!\n"
                        f"Game ID: `{active_game[0]}`\n"
                        f"Use /current_game to see details\nor /leade to leave the game.",
                        parse_mode="HTML",
                    )
                    return

                # Try to join the game
                game_id, opponent_id = self.game_manager.join_game(invite_link, user.id)

                if game_id:
                    # Get the initial board state
                    board = chess.Board()

                    # Determine if user is white or black
                    game_info = self.game_manager.get_game(game_id)
                    is_white = game_info["player1_id"] == user.id
                    color = "White ♙" if is_white else "Black ♟"

                    with open("start.png", "rb") as f:
                        await update.message.reply_photo(
                            photo=f,
                            caption=(
                                f"✅ Successfully joined game!\n\n"
                                f"Game ID: `{game_id}`\n"
                                f"You are: {color}\n\n"
                                f"{'It\'s your turn!' if is_white else f'Waiting for opponent to move...'}"
                            ),
                            parse_mode="HTML",
                        )

                    # Notify the other player
                    if opponent_id:
                        is_white = game_info["player2_id"] == user.id
                        try:
                            with open("start.png", "rb") as f:
                                await context.bot.send_photo(
                                    chat_id=opponent_id,
                                    photo=f,
                                    caption=(
                                        f"✅ {user.username} has joined game!\n\n"
                                        f"Game ID: `{game_id}`\n"
                                        f"You are: {color}\n\n"
                                        f"{f'It\'s your turn! You are {color}' if is_white else f'Waiting for opponent to move...'}"
                                    ),
                                    parse_mode="HTML",
                                )
                        except Exception:
                            pass
                else:
                    await update.message.reply_text(
                        "❌ Invalid or expired invite link!\n\n"
                        "Possible reasons:\n"
                        "• Game already has 2 players\n"
                        "• Game doesn't exist\n"
                        "• Link is expired\n\n"
                        "Create your own game with /newgame"
                    )
                return

        # Regular /start without parameters
        welcome_message = (
            "<b>Welcome to CheZZ!</b>\n\n"
            "<b>Commands:</b>\n"
            "/newgame - Start a new game\n"
            "/join [code] - Join a game\n"
            "/current_game - Show your current game\n"
            "/leave - Leave current game (forfeit)\n\n"
            "<b>How to play:</b>\n"
            "Just type moves like e2e4, Nf3, or O-O"
        )
        await update.message.reply_text(welcome_message, parse_mode="HTML")

    async def new_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start a new game."""
        player_id = update.effective_user.id

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
                f"You're already in an active game ({active_game[0]})!"
            )
            return

        # Create a new game
        game_id, invite_link = self.game_manager.create_game(player_id)

        deep_link = f"https://t.me/{BOT_NAME}?start=join_{invite_link}"

        invite_message = (
            "<b>New chess game created!</b>\n\n"
            f"<b>Game ID:</b> <code>{game_id}</code>\n"
            f"<b>Invite code:</b> <code>{invite_link}</code>\n\n"
            f"<b>Share this link to invite a friend:</b>\n{deep_link}\n\n"
            f"<b>Or they can use:</b>\n<code>/join {invite_link}</code>"
        )
        await update.message.reply_text(invite_message, parse_mode="HTML")

    async def join_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Join a game using an invite link."""
        player_id = update.effective_user.id

        # Check if user provided an invite link
        if len(context.args) != 1:
            await update.message.reply_text("Usage: /join [game_id]")
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
                f"You're already in an active game ({active_game[0]})!"
            )
            return

        # Try to join the game
        game_id, opponent_id = self.game_manager.join_game(invite_link, player_id)

        if game_id:
            # Get the initial board state
            board = chess.Board()
            svg_file = self.render_board(board)

            with open(svg_file, "rb") as f:
                await update.message.reply_photo(
                    photo=f,
                    caption=f"Successfully joined game {game_id}!\n\nWhite ({update.effective_user.username}) starts. Waiting for first move...",
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
                        caption=f"Player {update.effective_user.username} has joined your game!\nGame ID: {game_id}",
                    )
                os.unlink(opponent_svg_file)
            except Exception:
                pass  # Ignore if unable to send message
        else:
            await update.message.reply_text("Invalid or expired invite link!")

    async def handle_move(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle chess moves."""
        player_id = update.effective_user.id
        move_text = update.message.text.strip().lower()

        if not self.is_valid_move_format(move_text):
            return  # Don't respond to non-move messages

        # Find the game this player is in
        conn = sqlite3.connect(self.game_manager.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT game_id FROM games 
            WHERE (player1_id = ? OR player2_id = ?) AND status = 'playing'
        """,
            (player_id, player_id),
        )
        result = cursor.fetchone()
        conn.close()

        if not result:
            await update.message.reply_text(
                "You're not in an active game. Start one with /newgame"
            )
            return

        game_id = result[0]

        # Make the move
        result = self.game_manager.make_move(game_id, move_text, player_id)

        if result["success"]:
            # Get updated game info
            game_info = self.game_manager.get_game(game_id)

            # Create the board
            board = chess.Board(result["new_fen"])

            # Get SVG file path
            svg_file = self.render_board(board)

            # Determine who's turn it is now
            current_player = (
                "White"
                if game_info["current_turn"] == game_info["player1_id"]
                else "Black"
            )

            # Prepare caption (same as before)
            if result["status"] == "finished":
                if result["winner"] == "draw":
                    caption = f"Game ended in a draw!"
                else:
                    winner_name = "You" if result["winner"] == player_id else "Opponent"
                    caption = f"Checkmate! {winner_name} wins!"

                # Delete the finished game
                self.game_manager.delete_game(game_id)
            else:
                caption = f"Move: {move_text}\nCurrent turn: {current_player}"

            # Send SVG as document
            with open(svg_file, "rb") as f:
                await update.message.reply_photo(
                    photo=f, caption=caption, parse_mode="HTML"
                )

            # Clean up temp file
            os.unlink(svg_file)

            # Notify the other player
            other_player_id = (
                game_info["player2_id"]
                if player_id == game_info["player1_id"]
                else game_info["player1_id"]
            )
            try:
                # Create another SVG for the opponent
                opponent_svg_file = self.render_board(board)
                opponent_caption = f"Your turn! Opponent {update.effective_user.username} played {move_text}"

                with open(opponent_svg_file, "rb") as f:
                    await context.bot.send_photo(
                        chat_id=other_player_id,
                        photo=f,
                        caption=opponent_caption,
                    )

                # Clean up temp file
                os.unlink(opponent_svg_file)

            except Exception:
                pass  # Ignore if unable to send message
        else:
            await update.message.reply_text(f"Invalid move: {result['error']}")

    def is_valid_move_format(self, move_text):
        """Check if the move format is potentially valid."""
        # Matches standard algebraic notation like e4, Nf3, O-O, etc.
        pattern = r"^([a-h][1-8][a-h][1-8]|[a-h][1-8]|O-O(-O)?|N[a-h][1-8]?|B[a-h][1-8]?|R[a-h][1-8]?|Q[a-h][1-8]?|K[a-h][1-8]?)$"
        return bool(re.match(pattern, move_text.lower()))

    def render_board(self, board, game_id=None):
        """Render the chess board as a PNG image and return file path."""
        import cairosvg
        import time
        import random

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
        player_id = update.effective_user.id

        # Find the user's active game
        conn = sqlite3.connect(self.game_manager.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT g.game_id, g.player1_id, g.player2_id, g.created_at
            FROM games g
            WHERE (g.player1_id = ? OR g.player2_id = ?) AND g.status = 'playing'
        """,
            (player_id, player_id),
        )

        result = cursor.fetchone()
        conn.close()

        if not result:
            await update.message.reply_text(
                "You don't have any active games. Start one with /newgame"
            )
            return

        game_id, player1_id, player2_id, created_at = result

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

        # Format the response
        game_info_message = (
            f"Current Active Game:"
            f"\nID: {game_id}"
            f"\nOpponent: {opponent_name}"
            f"\nStarted at: {created_at}"
        )

        await update.message.reply_text(game_info_message)

    async def leave_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Leave the current game immediately."""
        player_id = update.effective_user.id
        username = update.effective_user.username or update.effective_user.first_name

        # Find the user's active game
        conn = sqlite3.connect(self.game_manager.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT g.game_id, 
                CASE 
                    WHEN g.player1_id = ? THEN g.player2_id 
                    ELSE g.player1_id 
                END as opponent_id
            FROM games g
            WHERE (g.player1_id = ? OR player2_id = ?) AND status = 'playing'
        """,
            (player_id, player_id, player_id),
        )

        result = cursor.fetchone()

        if not result:
            await update.message.reply_text(
                "❌ No active game found.\n" "You can start a new one with /newgame"
            )
            conn.close()
            return

        game_id, opponent_id = result

        # Delete the game
        self.game_manager.delete_game(game_id)

        # Notify the player who left
        await update.message.reply_text(
            "<b>Game ended.</b>\n\n"
            f"You have left game <code>{game_id}</code>.\n"
            f"Your opponent wins by forfeit.\n\n"
            f"Start a new game anytime with <code>/newgame</code>",
            parse_mode="HTML",
        )

        # Notify the opponent
        if opponent_id:
            try:
                await context.bot.send_message(
                    chat_id=opponent_id,
                    text="<b>Victory by forfeit!</b>\n\n"
                    f"Player <b>{username}</b> has left game <code>{game_id}</code>.\n"
                    f"You are awarded the win! 🎉\n\n"
                    f"Start a new game with <code>/newgame</code>",
                    parse_mode="HTML",
                )
            except Exception as e:
                print(f"Note: Could not notify opponent {opponent_id}: {e}")

            conn.close()

    def run(self):
        """Run the bot."""
        print("Starting chess bot...")
        self.application.run_polling()
