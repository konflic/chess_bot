#!/usr/bin/env python3
"""
Chess Bot Module
Separate module containing the ChessBot class and related logic.
"""

import sqlite3
import random
import string
import chess  # This imports the python-chess library (not our file)
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio
import re

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
        cursor.execute('''
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
        ''')
        
        # Create moves table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS moves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT,
                move_san TEXT,
                player_id INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (game_id) REFERENCES games (game_id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def generate_invite_link(self):
        """Generate a unique invite link for a game."""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    
    def create_game(self, player1_id):
        """Create a new game and return the game ID and invite link."""
        game_id = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
        invite_link = self.generate_invite_link()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO games (game_id, player1_id, current_turn, invite_link)
                VALUES (?, ?, ?, ?)
            ''', (game_id, player1_id, player1_id, invite_link))
            
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
        
        cursor.execute('''
            SELECT game_id, player1_id FROM games 
            WHERE invite_link = ? AND player2_id IS NULL AND status = 'waiting'
        ''', (invite_link,))
        
        result = cursor.fetchone()
        if result:
            game_id, player1_id = result
            
            # Update the game to add player2 and start the game
            cursor.execute('''
                UPDATE games 
                SET player2_id = ?, status = 'playing'
                WHERE game_id = ?
            ''', (player2_id, game_id))
            
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
        
        cursor.execute('''
            SELECT game_id, player1_id, player2_id, fen, current_turn, status
            FROM games WHERE game_id = ?
        ''', (game_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'game_id': result[0],
                'player1_id': result[1],
                'player2_id': result[2],
                'fen': result[3],
                'current_turn': result[4],
                'status': result[5]
            }
        return None
    
    def make_move(self, game_id, move_san, player_id):
        """Make a move in the game."""
        game = self.get_game(game_id)
        if not game:
            return {'success': False, 'error': 'Game not found'}
        
        if game['current_turn'] != player_id:
            return {'success': False, 'error': 'Not your turn'}
        
        # Load the current position
        board = chess.Board(game['fen'])
        
        # Try to make the move
        try:
            move = board.parse_san(move_san)
            if board.is_legal(move):
                board.push(move)
                
                # Check game status
                if board.is_checkmate():
                    game_status = 'finished'
                    winner = player_id
                elif board.is_stalemate() or board.is_insufficient_material() or board.can_claim_draw():
                    game_status = 'finished'
                    winner = 'draw'
                else:
                    # Switch turns
                    next_player = game['player2_id'] if player_id == game['player1_id'] else game['player1_id']
                    game_status = 'playing'
                    winner = None
                
                # Update the game
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute('''
                    UPDATE games 
                    SET fen = ?, current_turn = ?, status = ?
                    WHERE game_id = ?
                ''', (board.fen(), next_player if game_status == 'playing' else game['current_turn'], game_status, game_id))
                
                # Save the move
                cursor.execute('''
                    INSERT INTO moves (game_id, move_san, player_id)
                    VALUES (?, ?, ?)
                ''', (game_id, move_san, player_id))
                
                conn.commit()
                conn.close()
                
                return {
                    'success': True,
                    'new_fen': board.fen(),
                    'next_turn': next_player if game_status == 'playing' else None,
                    'checkmate': board.is_checkmate(),
                    'stalemate': board.is_stalemate(),
                    'insufficient_material': board.is_insufficient_material(),
                    'winner': winner,
                    'status': game_status
                }
            else:
                return {'success': False, 'error': 'Illegal move'}
        except ValueError:
            return {'success': False, 'error': 'Invalid move notation'}
    
    def delete_game(self, game_id):
        """Delete a finished game from the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM games WHERE game_id = ?', (game_id,))
        cursor.execute('DELETE FROM moves WHERE game_id = ?', (game_id,))
        
        conn.commit()
        conn.close()


class ChessBot:
    def __init__(self, token_file='TOKEN'):
        # Read the bot token
        with open(token_file, 'r') as f:
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
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_move))
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /start command."""
        welcome_message = (
            "Welcome to Telegram Chess!\n\n"
            "Commands:\n"
            "/newgame - Start a new game\n"
            "/join [link] - Join a game using an invite link\n"\
            "/current_game - Show your current active game information\n\n"
            "To make moves, simply type the move in algebraic notation (e.g., 'e2e4' or 'Nf3')"
        )
        await update.message.reply_text(welcome_message)
    
    async def new_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start a new game."""
        player_id = update.effective_user.id
        
        # Check if user is already in a game
        conn = sqlite3.connect(self.game_manager.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT game_id FROM games 
            WHERE (player1_id = ? OR player2_id = ?) AND status = 'playing'
        ''', (player_id, player_id))
        active_game = cursor.fetchone()
        conn.close()
        
        if active_game:
            await update.message.reply_text(f"You're already in an active game ({active_game[0]})!")
            return
        
        # Create a new game
        game_id, invite_link = self.game_manager.create_game(player_id)
        
        invite_message = (
            f"New game created!\n"
            f"Game ID: {game_id}\n"
            f"Invite link: https://t.me/{BOT_NAME}?join={invite_link}\n\n"
            f"Send this link to someone to play against them!"
        )
        await update.message.reply_text(invite_message)
    
    async def join_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Join a game using an invite link."""
        player_id = update.effective_user.id
        
        # Check if user provided an invite link
        if len(context.args) != 1:
            await update.message.reply_text("Usage: /join [invite_link]")
            return
        
        invite_link = context.args[0]
        
        # Check if user is already in a game
        conn = sqlite3.connect(self.game_manager.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT game_id FROM games 
            WHERE (player1_id = ? OR player2_id = ?) AND status = 'playing'
        ''', (player_id, player_id))
        active_game = cursor.fetchone()
        conn.close()
        
        if active_game:
            await update.message.reply_text(f"You're already in an active game ({active_game[0]})!")
            return
        
        # Try to join the game
        game_id, opponent_id = self.game_manager.join_game(invite_link, player_id)
        
        if game_id:
            # Get the initial board state
            board = chess.Board()
            await update.message.reply_text(
                f"Successfully joined game {game_id}!\n\n{self.render_board(board)}\n\n"
                f"White (Player 1) starts. Waiting for first move..."
            )
            
            # Notify the other player
            try:
                await context.bot.send_message(
                    chat_id=opponent_id,
                    text=f"Player has joined your game! Game ID: {game_id}\n\n{self.render_board(board)}"
                )
            except Exception:
                pass  # Ignore if unable to send message
        else:
            await update.message.reply_text("Invalid or expired invite link!")
    
    async def handle_move(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle chess moves."""
        player_id = update.effective_user.id
        move_text = update.message.text.strip()
        
        # Validate move format (should be like "e2e4" or "Nf3")
        if not self.is_valid_move_format(move_text):
            return  # Don't respond to non-move messages
        
        # Find the game this player is in
        conn = sqlite3.connect(self.game_manager.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT game_id FROM games 
            WHERE (player1_id = ? OR player2_id = ?) AND status = 'playing'
        ''', (player_id, player_id))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            await update.message.reply_text("You're not in an active game. Start one with /newgame")
            return
        
        game_id = result[0]
        
        # Make the move
        result = self.game_manager.make_move(game_id, move_text, player_id)
        
        if result['success']:
            # Get updated game info
            game_info = self.game_manager.get_game(game_id)
            
            # Render the board
            board = chess.Board(result['new_fen'])
            board_render = self.render_board(board)
            
            # Determine who's turn it is now
            current_player = "White" if game_info['current_turn'] == game_info['player1_id'] else "Black"
            
            # Prepare message
            if result['status'] == 'finished':
                if result['winner'] == 'draw':
                    message = f"Game ended in a draw!\n\n{board_render}"
                else:
                    winner_name = "You" if result['winner'] == player_id else "Opponent"
                    message = f"Checkmate! {winner_name} wins!\n\n{board_render}"
                
                # Delete the finished game
                self.game_manager.delete_game(game_id)
            else:
                message = f"Move: {move_text}\nCurrent turn: {current_player}\n\n{board_render}"
            
            await update.message.reply_text(message)
            
            # Notify the other player
            other_player_id = game_info['player2_id'] if player_id == game_info['player1_id'] else game_info['player1_id']
            try:
                notification_message = f"Your turn! Opponent played {move_text}\n\n{board_render}"
                await context.bot.send_message(
                    chat_id=other_player_id,
                    text=notification_message
                )
            except Exception:
                pass  # Ignore if unable to send message
        else:
            await update.message.reply_text(f"Invalid move: {result['error']}")
    
    def is_valid_move_format(self, move_text):
        """Check if the move format is potentially valid."""
        # Matches standard algebraic notation like e4, Nf3, O-O, etc.
        pattern = r'^([a-h][1-8][a-h][1-8]|[a-h][1-8]|O-O(-O)?|N[a-h][1-8]?|B[a-h][1-8]?|R[a-h][1-8]?|Q[a-h][1-8]?|K[a-h][1-8]?)$'
        return bool(re.match(pattern, move_text.lower()))
    
    def render_board(self, board):
        """Render the chess board as a text representation."""
        # Convert the board to a string representation
        fen = board.fen()
        rows = fen.split(' ')[0].split('/')
        
        # Map pieces to Unicode characters
        piece_symbols = {
            'p': '♟', 'r': '♜', 'n': '♞', 'b': '♝', 'q': '♛', 'k': '♚',  # Black
            'P': '♙', 'R': '♖', 'N': '♘', 'B': '♗', 'Q': '♕', 'K': '♔'   # White
        }
        
        board_str = "  a b c d e f g h\n"
        for i, row in enumerate(rows):
            board_str += f"{8-i} "
            for char in row:
                if char.isdigit():
                    # Empty squares
                    board_str += ". " * int(char)
                else:
                    board_str += piece_symbols[char] + " "
            board_str += f"{8-i}\n"
        board_str += "  a b c d e f g h"
        
        return board_str
    
    async def current_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's current active game information."""
        player_id = update.effective_user.id
        
        # Find the user's active game
        conn = sqlite3.connect(self.game_manager.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT g.game_id, g.player1_id, g.player2_id, g.created_at
            FROM games g
            WHERE (g.player1_id = ? OR g.player2_id = ?) AND g.status = 'playing'
        """, (player_id, player_id))
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            await update.message.reply_text("You don't have any active games. Start one with /newgame")
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

    def run(self):
        """Run the bot."""
        print("Starting chess bot...")
        self.application.run_polling()