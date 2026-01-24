#!/usr/bin/env python3
"""
Test script for the chess bot functionality
"""

from chess import ChessGame, Position, Color, PieceType
from bot import ChessBot


def test_chess_game():
    """Test basic chess game functionality."""
    print("Testing Chess Game Logic...")
    
    # Create a new game
    game = ChessGame()
    
    print("\nInitial Board:")
    game.print_board()
    
    # Test some basic moves
    print("\nTesting a basic move (e2 to e4):")
    from_pos = Position(6, 4)  # e2 (0-indexed: row 6, col 4)
    to_pos = Position(4, 4)    # e4 (0-indexed: row 4, col 4)
    
    if game.make_move(from_pos, to_pos):
        print("Move successful!")
        print(f"Current player: {game.current_player.value}")
        game.print_board()
    else:
        print("Move failed!")
    
    print("\nTesting invalid move (own piece capture attempt):")
    # Try to move white piece again (should fail as it's black's turn)
    another_from = Position(7, 3)  # Queen at d1
    another_to = Position(5, 3)    # To d3
    if game.make_move(another_from, another_to):
        print("Unexpected success!")
    else:
        print("Correctly rejected move out of turn")
    
    print("\nTesting pawn capture pattern...")
    # Reset game for fresh test
    game2 = ChessGame()
    
    # Move a pawn to allow for capture testing
    game2.make_move(Position(6, 4), Position(4, 4))  # e2-e4
    game2.make_move(Position(1, 3), Position(3, 3))  # d7-d5 (black pawn)
    
    print("Board after e4 and d5:")
    game2.print_board()


def test_chess_bot():
    """Test chess bot functionality."""
    print("\n" + "="*50)
    print("Testing Chess Bot...")
    
    bot = ChessBot()
    
    print("Bot initialized successfully!")
    print(f"Active games: {len(bot.active_games)}")
    print(f"Waiting players: {len(bot.waiting_players)}")


if __name__ == "__main__":
    test_chess_game()
    test_chess_bot()
    print("\nAll tests completed!")