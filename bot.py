#!/usr/bin/env python3
"""
Telegram Chess Bot - Main entry point
This file provides a simple interface to run the chess bot.
"""

from chess_bot import ChessBot

def main():
    """Main function to run the chess bot."""
    bot = ChessBot()
    bot.run()

if __name__ == "__main__":
    main()