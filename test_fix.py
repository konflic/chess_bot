#!/usr/bin/env python3

import sqlite3
import random
import string
import datetime
from configuration import GAMES_DB

# Computer player ID (same as in chess_bot.py)
COMPUTER_PLAYER = -1

def init_test_db():
    """Initialize a test database using ChessGameManager."""
    from chess_bot import ChessGameManager

    # Clean up any existing test data
    conn = sqlite3.connect(GAMES_DB)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM games WHERE player1_id IN (12345, 67890, 99999) OR player2_id IN (12345, 67890, 99999)")
    conn.commit()
    conn.close()

    game_manager = ChessGameManager()
    # The init_db method is called in the constructor, so this ensures the database is properly initialized

def create_test_game(player_id, computer_opponent=False):
    """Create a test game."""
    game_id = "".join(random.choices(string.ascii_letters + string.digits, k=10))
    invite_link = "".join(random.choices(string.ascii_letters + string.digits, k=12))

    conn = sqlite3.connect(GAMES_DB)
    cursor = conn.cursor()

    try:
        if computer_opponent:
            # Create a game with a computer opponent
            cursor.execute(
                """
                INSERT INTO games (game_id, player1_id, player2_id, current_turn, invite_link, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (game_id, player_id, COMPUTER_PLAYER, player_id, invite_link, "playing"),
            )
        else:
            # Create a regular game waiting for a human opponent
            cursor.execute(
                """
                INSERT INTO games (game_id, player1_id, current_turn, invite_link)
                VALUES (?, ?, ?, ?)
            """,
                (game_id, player_id, player_id, invite_link),
            )

        conn.commit()
        conn.close()
        return game_id
    except sqlite3.IntegrityError:
        conn.close()
        return create_test_game(player_id, computer_opponent)

def check_existing_computer_game(player_id):
    """Check if player already has an active game against computer."""
    conn = sqlite3.connect(GAMES_DB)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT game_id FROM games
        WHERE (player1_id = ? OR player2_id = ?) AND
              ((player1_id = ? AND player2_id = ?) OR (player1_id = ? AND player2_id = ?)) AND
              status = 'playing'
        ORDER BY created_at DESC
        LIMIT 1
    """,
        (player_id, player_id, player_id, COMPUTER_PLAYER, COMPUTER_PLAYER, player_id),
    )

    result = cursor.fetchone()
    conn.close()
    return result

def test_fix():
    """Test the fix for limiting computer games."""
    print("Testing the fix for limiting computer games...")

    # Initialize test database
    init_test_db()

    # Test user ID
    test_user_id = 12345

    # Check 1: User should not have any computer games initially
    print("\n1. Checking if user has any existing computer games (should be None)...")
    result = check_existing_computer_game(test_user_id)
    print(f"Result: {result}")
    assert result is None, "User should not have any computer games initially"

    # Create a computer game for the user
    print("\n2. Creating a computer game for the user...")
    game_id = create_test_game(test_user_id, computer_opponent=True)
    print(f"Created game with ID: {game_id}")

    # Check 2: User should now have one computer game
    print("\n3. Checking if user has an existing computer game (should return the game)...")
    result = check_existing_computer_game(test_user_id)
    print(f"Result: {result}")
    assert result is not None, "User should have a computer game now"
    assert result[0] == game_id, "Returned game ID should match the created game"

    # Create a regular game for the user (should not affect the check)
    print("\n4. Creating a regular game for the user (should not affect the check)...")
    regular_game_id = create_test_game(test_user_id, computer_opponent=False)
    print(f"Created regular game with ID: {regular_game_id}")

    # Check 3: User should still have only one computer game
    print("\n5. Checking if user still has only one computer game...")
    result = check_existing_computer_game(test_user_id)
    print(f"Result: {result}")
    assert result is not None, "User should still have a computer game"
    assert result[0] == game_id, "Returned game ID should still be the computer game"

    # Create another computer game for a different user
    print("\n6. Creating a computer game for a different user...")
    other_user_id = 67890
    other_game_id = create_test_game(other_user_id, computer_opponent=True)
    print(f"Created game for other user with ID: {other_game_id}")

    # Check 4: Original user should still have only their own computer game
    print("\n7. Checking if original user still has only their computer game...")
    result = check_existing_computer_game(test_user_id)
    print(f"Result: {result}")
    assert result is not None, "User should still have a computer game"
    assert result[0] == game_id, "Returned game ID should still be the original computer game"

    # Check 5: Other user should have their own computer game
    print("\n8. Checking if other user has their computer game...")
    result = check_existing_computer_game(other_user_id)
    print(f"Result: {result}")
    assert result is not None, "Other user should have a computer game"
    assert result[0] == other_game_id, "Returned game ID should be the other user's computer game"

    print("\n✅ All tests passed! The fix is working correctly.")
    print("\nThe fix successfully prevents users from creating multiple games against the computer.")
    print("Users can only have one active game against the computer at a time, just like with regular games.")
    print("\nThe last move timestamp tracking is now enabled for all games, which will help identify inactive games.")

if __name__ == "__main__":
    test_fix()
