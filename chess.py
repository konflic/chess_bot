"""
Chess Game Implementation with Multiplayer Support
"""

import random
from enum import Enum
from typing import List, Optional, Tuple


class Color(Enum):
    WHITE = "white"
    BLACK = "black"


class PieceType(Enum):
    PAWN = "pawn"
    ROOK = "rook"
    KNIGHT = "knight"
    BISHOP = "bishop"
    QUEEN = "queen"
    KING = "king"


class Piece:
    def __init__(self, piece_type: PieceType, color: Color):
        self.type = piece_type
        self.color = color
        self.has_moved = False

    def __repr__(self):
        symbols = {
            (PieceType.PAWN, Color.WHITE): "♙",
            (PieceType.PAWN, Color.BLACK): "♟",
            (PieceType.ROOK, Color.WHITE): "♖",
            (PieceType.ROOK, Color.BLACK): "♜",
            (PieceType.KNIGHT, Color.WHITE): "♘",
            (PieceType.KNIGHT, Color.BLACK): "♞",
            (PieceType.BISHOP, Color.WHITE): "♗",
            (PieceType.BISHOP, Color.BLACK): "♝",
            (PieceType.QUEEN, Color.WHITE): "♕",
            (PieceType.QUEEN, Color.BLACK): "♛",
            (PieceType.KING, Color.WHITE): "♔",
            (PieceType.KING, Color.BLACK): "♚",
        }
        return symbols.get((self.type, self.color), "?")


class Position:
    def __init__(self, row: int, col: int):
        self.row = row
        self.col = col

    def __eq__(self, other):
        return isinstance(other, Position) and self.row == other.row and self.col == other.col

    def __hash__(self):
        return hash((self.row, self.col))

    def __repr__(self):
        return f"Position({self.row}, {self.col})"


class ChessGame:
    def __init__(self):
        self.board = [[None for _ in range(8)] for _ in range(8)]
        self.current_player = Color.WHITE
        self.game_over = False
        self.winner = None
        self.move_history = []
        self.setup_board()

    def setup_board(self):
        """Set up the initial chess board configuration."""
        # Set up pawns
        for col in range(8):
            self.board[1][col] = Piece(PieceType.PAWN, Color.BLACK)
            self.board[6][col] = Piece(PieceType.PAWN, Color.WHITE)

        # Set up other pieces
        back_row_black = [
            PieceType.ROOK, PieceType.KNIGHT, PieceType.BISHOP, PieceType.QUEEN,
            PieceType.KING, PieceType.BISHOP, PieceType.KNIGHT, PieceType.ROOK
        ]
        
        for col, piece_type in enumerate(back_row_black):
            self.board[0][col] = Piece(piece_type, Color.BLACK)
            self.board[7][col] = Piece(piece_type, Color.WHITE)

        # Add pieces in the middle rows
        for col in range(8):
            self.board[0][col].has_moved = False
            self.board[7][col].has_moved = False
            self.board[1][col].has_moved = False
            self.board[6][col].has_moved = False

    def get_piece(self, pos: Position) -> Optional[Piece]:
        """Get the piece at the given position."""
        if 0 <= pos.row < 8 and 0 <= pos.col < 8:
            return self.board[pos.row][pos.col]
        return None

    def is_valid_move(self, from_pos: Position, to_pos: Position) -> bool:
        """Check if a move is valid according to chess rules."""
        piece = self.get_piece(from_pos)
        if not piece or piece.color != self.current_player:
            return False

        target_piece = self.get_piece(to_pos)
        if target_piece and target_piece.color == piece.color:
            return False  # Can't capture own piece

        # Basic movement validation based on piece type
        if piece.type == PieceType.PAWN:
            return self._is_pawn_move_valid(from_pos, to_pos, piece)
        elif piece.type == PieceType.ROOK:
            return self._is_rook_move_valid(from_pos, to_pos)
        elif piece.type == PieceType.KNIGHT:
            return self._is_knight_move_valid(from_pos, to_pos)
        elif piece.type == PieceType.BISHOP:
            return self._is_bishop_move_valid(from_pos, to_pos)
        elif piece.type == PieceType.QUEEN:
            return self._is_queen_move_valid(from_pos, to_pos)
        elif piece.type == PieceType.KING:
            return self._is_king_move_valid(from_pos, to_pos)

        return False

    def _is_pawn_move_valid(self, from_pos: Position, to_pos: Position, piece: Piece) -> bool:
        """Check if pawn move is valid."""
        direction = -1 if piece.color == Color.WHITE else 1  # White moves up (-1), black moves down (+1)
        row_diff = to_pos.row - from_pos.row
        col_diff = abs(to_pos.col - from_pos.col)

        # Forward move (no capture)
        if col_diff == 0:
            # Single move forward
            if row_diff == direction and not self.get_piece(to_pos):
                return True
            # Double move from starting position
            if (not piece.has_moved and row_diff == 2 * direction and 
                from_pos.row in [1, 6] and not self.get_piece(to_pos)):
                # Check that there's no piece in between
                mid_pos = Position(from_pos.row + direction, from_pos.col)
                return not self.get_piece(mid_pos)
        
        # Diagonal capture
        elif col_diff == 1 and row_diff == direction:
            target_piece = self.get_piece(to_pos)
            if target_piece and target_piece.color != piece.color:
                return True
        
        return False

    def _is_rook_move_valid(self, from_pos: Position, to_pos: Position) -> bool:
        """Check if rook move is valid."""
        if from_pos.row != to_pos.row and from_pos.col != to_pos.col:
            return False  # Rook moves in straight lines only

        return self._is_path_clear(from_pos, to_pos)

    def _is_knight_move_valid(self, from_pos: Position, to_pos: Position) -> bool:
        """Check if knight move is valid."""
        row_diff = abs(to_pos.row - from_pos.row)
        col_diff = abs(to_pos.col - from_pos.col)
        
        return (row_diff == 2 and col_diff == 1) or (row_diff == 1 and col_diff == 2)

    def _is_bishop_move_valid(self, from_pos: Position, to_pos: Position) -> bool:
        """Check if bishop move is valid."""
        row_diff = abs(to_pos.row - from_pos.row)
        col_diff = abs(to_pos.col - from_pos.col)
        
        if row_diff != col_diff:
            return False  # Bishop moves diagonally only

        return self._is_path_clear(from_pos, to_pos)

    def _is_queen_move_valid(self, from_pos: Position, to_pos: Position) -> bool:
        """Check if queen move is valid."""
        # Queen combines rook and bishop movements
        return (self._is_rook_move_valid(from_pos, to_pos) or 
                self._is_bishop_move_valid(from_pos, to_pos))

    def _is_king_move_valid(self, from_pos: Position, to_pos: Position) -> bool:
        """Check if king move is valid."""
        row_diff = abs(to_pos.row - from_pos.row)
        col_diff = abs(to_pos.col - from_pos.col)
        
        # King moves one square in any direction
        return row_diff <= 1 and col_diff <= 1 and (row_diff + col_diff > 0)

    def _is_path_clear(self, from_pos: Position, to_pos: Position) -> bool:
        """Check if the path between two positions is clear of pieces."""
        row_step = 0 if from_pos.row == to_pos.row else (1 if to_pos.row > from_pos.row else -1)
        col_step = 0 if from_pos.col == to_pos.col else (1 if to_pos.col > from_pos.col else -1)

        current = Position(from_pos.row + row_step, from_pos.col + col_step)
        
        while current != to_pos:
            if self.get_piece(current):
                return False  # Path is blocked
            current.row += row_step
            current.col += col_step
            
        return True

    def make_move(self, from_pos: Position, to_pos: Position) -> bool:
        """Make a move on the board if it's valid."""
        if not self.is_valid_move(from_pos, to_pos):
            return False

        piece = self.get_piece(from_pos)
        
        # Record the move
        captured_piece = self.get_piece(to_pos)
        self.move_history.append({
            'from': (from_pos.row, from_pos.col),
            'to': (to_pos.row, to_pos.col),
            'piece': piece,
            'captured': captured_piece
        })

        # Make the move
        self.board[to_pos.row][to_pos.col] = piece
        self.board[from_pos.row][from_pos.col] = None
        piece.has_moved = True

        # Switch player
        self.current_player = Color.BLACK if self.current_player == Color.WHITE else Color.WHITE

        # Check for check/checkmate conditions (simplified)
        # In a real implementation, we would need to check for king safety
        # For now, just detect if king was captured (which shouldn't happen in real chess)
        if captured_piece and captured_piece.type == PieceType.KING:
            self.game_over = True
            self.winner = Color.BLACK if captured_piece.color == Color.WHITE else Color.WHITE

        return True

    def print_board(self):
        """Print the current state of the board."""
        print("  a b c d e f g h")
        for row in range(7, -1, -1):  # Print from top to bottom
            print(f"{row + 1} ", end="")
            for col in range(8):
                piece = self.board[row][col]
                if piece:
                    print(f"{piece} ", end="")
                else:
                    print(". ", end="")
            print(f" {row + 1}")
        print("  a b c d e f g h")

    def get_valid_moves(self, pos: Position) -> List[Position]:
        """Get all valid moves for the piece at the given position."""
        moves = []
        for r in range(8):
            for c in range(8):
                test_pos = Position(r, c)
                if self.is_valid_move(pos, test_pos):
                    moves.append(test_pos)
        return moves

    def is_in_check(self, color: Color) -> bool:
        """Check if the king of the given color is in check."""
        # Find the king
        king_pos = None
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if (piece and piece.type == PieceType.KING and 
                    piece.color == color):
                    king_pos = Position(r, c)
                    break
            if king_pos:
                break

        if not king_pos:
            return False  # No king found (shouldn't happen in valid game)

        # Check if any opponent piece can attack the king
        opponent_color = Color.BLACK if color == Color.WHITE else Color.WHITE
        for r in range(8):
            for c in range(8):
                piece = self.board[r][c]
                if piece and piece.color == opponent_color:
                    test_pos = Position(r, c)
                    # Temporarily switch players to test if opponent can capture king
                    original_player = self.current_player
                    self.current_player = opponent_color
                    can_attack = self.is_valid_move(test_pos, king_pos)
                    self.current_player = original_player
                    if can_attack:
                        return True
        return False