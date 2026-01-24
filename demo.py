#!/usr/bin/env python3
"""
Demo script showing the chess bot capabilities
"""

from chess import ChessGame, Position, Color
import time


def demo_chess_game():
    """Demonstrate the chess game functionality."""
    print("="*60)
    print("DEMO: Chess Game Functionality")
    print("="*60)
    
    # Create a new game
    game = ChessGame()
    
    print("\n1. Initial Board Setup:")
    print("-" * 20)
    game.print_board()
    
    print(f"\nCurrent player: {game.current_player.value}")
    
    print("\n2. Making a Valid Move (White: e2 to e4)")
    print("-" * 40)
    # Move from e2 (row 6, col 4) to e4 (row 4, col 4)
    from_pos = Position(6, 4)  
    to_pos = Position(4, 4)
    
    if game.make_move(from_pos, to_pos):
        print("✓ Move e2e4 successful!")
        print(f"Now it's {game.current_player.value}'s turn")
        game.print_board()
    else:
        print("✗ Move failed!")
    
    print("\n3. Black's Turn (Black: e7 to e5)")
    print("-" * 35)
    # Move from e7 (row 1, col 4) to e5 (row 3, col 4)
    from_pos = Position(1, 4)  
    to_pos = Position(3, 4)
    
    if game.make_move(from_pos, to_pos):
        print("✓ Move e7e5 successful!")
        print(f"Now it's {game.current_player.value}'s turn")
        game.print_board()
    else:
        print("✗ Move failed!")
    
    print("\n4. Testing Knight Move (White: g1 to f3)")
    print("-" * 38)
    # Move white knight from g1 (row 7, col 6) to f3 (row 5, col 5)
    from_pos = Position(7, 6)  
    to_pos = Position(5, 5)
    
    if game.make_move(from_pos, to_pos):
        print("✓ Knight move g1f3 successful!")
        print(f"Now it's {game.current_player.value}'s turn")
        game.print_board()
    else:
        print("✗ Knight move failed!")
    
    print("\n5. Testing Invalid Move (attempting to move opponent's piece)")
    print("-" * 58)
    # Try to move black pawn again when it's white's turn
    from_pos = Position(3, 4)  # e5 (black pawn)
    to_pos = Position(2, 4)    # e6
    
    if game.make_move(from_pos, to_pos):
        print("✗ This should not happen - moved opponent's piece!")
    else:
        print("✓ Correctly prevented moving opponent's piece")
        print(f"It's still {game.current_player.value}'s turn")
    
    print("\n6. Testing Pawn Capture Pattern")
    print("-" * 32)
    # Reset and set up a capture scenario
    game2 = ChessGame()
    
    # Make some moves to set up a capture situation
    game2.make_move(Position(6, 4), Position(4, 4))  # e2e4
    game2.make_move(Position(1, 3), Position(3, 3))  # d7d5
    game2.make_move(Position(6, 3), Position(4, 3))  # d2d4
    game2.make_move(Position(3, 3), Position(4, 4))  # d5xe4 (capture!)
    
    print("After pawn capture d5xe4:")
    game2.print_board()
    
    print("\n7. Game Status Information")
    print("-" * 27)
    print(f"Game over: {game2.game_over}")
    print(f"Winner: {game2.winner}")
    print(f"Move history length: {len(game2.move_history)}")
    
    print("\n" + "="*60)
    print("DEMO COMPLETED SUCCESSFULLY!")
    print("="*60)


if __name__ == "__main__":
    demo_chess_game()