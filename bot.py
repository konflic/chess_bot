"""
Chess Bot with Multiplayer Support
This module implements a Telegram bot that allows users to play chess against each other.
"""

import os
import logging
from typing import Dict, Optional
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters
)

from chess import ChessGame, Position, Color, PieceType

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Define conversation states
WAITING_FOR_OPPONENT, GAME_ACTIVE = range(2)

class ChessBot:
    def __init__(self):
        self.active_games: Dict[int, ChessGame] = {}  # Maps chat_id to game
        self.waiting_players: Dict[str, int] = {}     # Maps game_id to waiting player
        self.player_game_map: Dict[int, str] = {}    # Maps user_id to game_id
        self.pending_moves: Dict[str, Position] = {} # Maps game_id to pending move

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /start command."""
        welcome_message = (
            "Welcome to Chess Bot! 🏁\n\n"
            "Commands:\n"
            "/newgame - Start a new chess game\n"
            "/join <game_id> - Join an existing game\n"
            "/help - Show this help message\n\n"
            "To make a move, send coordinates in algebraic notation (e.g. 'e2e4')"
        )
        await update.message.reply_text(welcome_message)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send help message."""
        help_text = (
            "Chess Bot Help:\n\n"
            "To start a game:\n"
            "1. Type /newgame to create a new game\n"
            "2. Share the game ID with your friend\n"
            "3. Wait for your friend to join with /join <game_id>\n\n"
            "To make moves:\n"
            "Send moves in algebraic notation (e.g. 'e2e4', 'g1f3')\n"
            "Or use standard chess notation like 'Nf3' for knights, 'O-O' for castling\n\n"
            "Other commands:\n"
            "/resign - Resign the current game\n"
            "/board - View the current board state\n"
            "/moves - Show possible moves for selected piece"
        )
        await update.message.reply_text(help_text)

    async def new_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start a new game and generate a game ID."""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Generate a simple game ID
        import uuid
        game_id = str(uuid.uuid4())[:8]
        
        # Create new game
        game = ChessGame()
        self.active_games[chat_id] = game
        
        # Map user to game
        self.player_game_map[user_id] = game_id
        
        # Create the game for the first player (white)
        response = (
            f"New chess game created!\n"
            f"Game ID: `{game_id}`\n"
            f"You are playing as WHITE.\n"
            f"Share this ID with your friend to join the game.\n"
            f"Waiting for opponent to join..."
        )
        
        keyboard = [[InlineKeyboardButton("Join this game", callback_data=f"join_{game_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(response, parse_mode="Markdown", reply_markup=reply_markup)
        
        # Store waiting info
        self.waiting_players[game_id] = user_id

    async def join_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Join an existing game."""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        if len(context.args) != 1:
            await update.message.reply_text("Usage: /join <game_id>")
            return
        
        game_id = context.args[0]
        
        # Check if game exists and is waiting for opponent
        if game_id not in self.waiting_players:
            await update.message.reply_text(f"Game with ID {game_id} not found or already started.")
            return
        
        # Get the first player
        first_player_id = self.waiting_players[game_id]
        
        # Remove from waiting list
        del self.waiting_players[game_id]
        
        # Add both players to game mapping
        self.player_game_map[user_id] = game_id
        self.player_game_map[first_player_id] = game_id
        
        # Set up the game in the chat
        if chat_id not in self.active_games:
            self.active_games[chat_id] = ChessGame()
        
        game = self.active_games[chat_id]
        
        # Send initial board
        board_str = self.format_board(game)
        response = (
            f"Game started! 🎮\n"
            f"You are playing as BLACK.\n"
            f"First player (WHITE) goes first.\n\n"
            f"{board_str}"
        )
        
        await update.message.reply_text(response)
        
        # Notify first player
        try:
            await context.bot.send_message(
                chat_id=first_player_id,
                text=f"Opponent joined game {game_id}. Game started! You play as WHITE."
            )
        except:
            pass  # First player might not have started the bot

    def format_board(self, game: ChessGame) -> str:
        """Format the chess board for display."""
        board_str = "```\n"
        board_str += "  a b c d e f g h\n"
        for row in range(7, -1, -1):  # Print from top to bottom
            board_str += f"{row + 1} "
            for col in range(8):
                piece = game.board[row][col]
                if piece:
                    board_str += f"{piece} "
                else:
                    board_str += ". "
            board_str += f" {row + 1}\n"
        board_str += "  a b c d e f g h\n"
        board_str += "```"
        return board_str

    async def handle_move(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle a move command from a player."""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Check if user is in a game
        if user_id not in self.player_game_map:
            await update.message.reply_text("You're not in a game. Use /newgame to start one.")
            return
        
        # Check if game exists in this chat
        if chat_id not in self.active_games:
            await update.message.reply_text("No active game in this chat.")
            return
        
        game = self.active_games[chat_id]
        
        # Check if it's this player's turn
        # We'll implement a simple system where we map user IDs to colors
        # For simplicity, assume first player is white, second is black
        game_id = self.player_game_map[user_id]
        all_players_in_game = [pid for pid, gid in self.player_game_map.items() if gid == game_id]
        
        if len(all_players_in_game) < 2:
            await update.message.reply_text("Waiting for opponent to join...")
            return
        
        # Determine player color based on order they joined
        first_player = min(all_players_in_game)
        current_color = Color.WHITE if user_id == first_player else Color.BLACK
        
        if game.current_player != current_color:
            await update.message.reply_text(f"It's not your turn. Current player: {game.current_player.value.upper()}")
            return
        
        # Parse the move (assuming algebraic notation like "e2e4")
        move_text = update.message.text.strip().lower()
        
        if len(move_text) != 4:
            await update.message.reply_text("Invalid move format. Use algebraic notation (e.g. 'e2e4').")
            return
        
        try:
            from_col = ord(move_text[0]) - ord('a')
            from_row = int(move_text[1]) - 1
            to_col = ord(move_text[2]) - ord('a')
            to_row = int(move_text[3]) - 1
            
            # Validate coordinates
            if not (0 <= from_col <= 7 and 0 <= from_row <= 7 and 0 <= to_col <= 7 and 0 <= to_row <= 7):
                await update.message.reply_text("Invalid coordinates. Use algebraic notation (e.g. 'e2e4').")
                return
            
            from_pos = Position(from_row, from_col)
            to_pos = Position(to_row, to_col)
            
            # Attempt the move
            if game.make_move(from_pos, to_pos):
                # Update the board display
                board_str = self.format_board(game)
                
                # Check for game end conditions
                if game.game_over:
                    winner_msg = f"Game over! Winner: {game.winner.value.upper()}" if game.winner else "Game ended in a draw."
                    await update.message.reply_text(f"{board_str}\n\n{winner_msg}")
                    
                    # Clean up the game
                    if chat_id in self.active_games:
                        del self.active_games[chat_id]
                else:
                    next_player = "WHITE" if game.current_player == Color.WHITE else "BLACK"
                    await update.message.reply_text(
                        f"{board_str}\n\nNext move: {next_player}'s turn"
                    )
            else:
                await update.message.reply_text("Invalid move. Please try again.")
        
        except Exception as e:
            logger.error(f"Error processing move: {e}")
            await update.message.reply_text("Invalid move format. Use algebraic notation (e.g. 'e2e4').")

    async def show_board(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show the current board state."""
        chat_id = update.effective_chat.id
        
        if chat_id not in self.active_games:
            await update.message.reply_text("No active game in this chat.")
            return
        
        game = self.active_games[chat_id]
        board_str = self.format_board(game)
        await update.message.reply_text(board_str)

    async def resign_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Resign from the current game."""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        if user_id not in self.player_game_map:
            await update.message.reply_text("You're not in a game.")
            return
        
        if chat_id not in self.active_games:
            await update.message.reply_text("No active game in this chat.")
            return
        
        # Find opponent
        game_id = self.player_game_map[user_id]
        all_players_in_game = [pid for pid, gid in self.player_game_map.items() if gid == game_id]
        opponent_id = [pid for pid in all_players_in_game if pid != user_id]
        
        game = self.active_games[chat_id]
        
        # Determine winner (the other player)
        first_player = min(all_players_in_game)
        resigner_color = Color.WHITE if user_id == first_player else Color.BLACK
        winner_color = Color.BLACK if resigner_color == Color.WHITE else Color.WHITE
        
        game.winner = winner_color
        game.game_over = True
        
        # Notify players
        await update.message.reply_text(f"You resigned. {winner_color.value.upper()} wins!")
        
        if opponent_id:
            try:
                await context.bot.send_message(
                    chat_id=opponent_id[0],
                    text=f"Your opponent resigned. {winner_color.value.upper()} wins!"
                )
            except:
                pass
        
        # Clean up
        if chat_id in self.active_games:
            del self.active_games[chat_id]

def main():
    """Run the bot."""
    # Create bot instance
    bot_instance = ChessBot()
    
    # Create application
    application = Application.builder().token(os.getenv("TELEGRAM_BOT_TOKEN")).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", bot_instance.start_command))
    application.add_handler(CommandHandler("help", bot_instance.help_command))
    application.add_handler(CommandHandler("newgame", bot_instance.new_game))
    application.add_handler(CommandHandler("join", bot_instance.join_game))
    application.add_handler(CommandHandler("board", bot_instance.show_board))
    application.add_handler(CommandHandler("resign", bot_instance.resign_game))
    
    # Handle moves (all text messages that aren't commands)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot_instance.handle_move))
    
    # Run the bot until the user presses Ctrl-C
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()