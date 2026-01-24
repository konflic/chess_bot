# Chess Bot with Multiplayer Support

A Python-based chess bot that enables multiplayer chess games via Telegram.

## Features

- Complete chess game implementation with all standard rules
- Multiplayer support via Telegram bot
- Turn-based gameplay with proper validation
- Visual board representation
- Game state tracking

## Requirements

- Python 3.8+
- python-telegram-bot library

## Installation

1. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up your Telegram bot token as an environment variable:
   ```bash
   export TELEGRAM_BOT_TOKEN="your_bot_token_here"
   ```

## Usage

### Running the Bot

```bash
python bot.py
```

### Bot Commands

- `/start` - Start interacting with the bot
- `/help` - Show help information
- `/newgame` - Create a new chess game
- `/join <game_id>` - Join an existing game
- `/board` - Display the current board state
- `/resign` - Resign from the current game

### Making Moves

To make a move, send coordinates in algebraic notation (e.g., 'e2e4' to move from e2 to e4).

## Architecture

- `chess.py`: Contains the core chess game logic and rules
- `bot.py`: Implements the Telegram bot interface and multiplayer functionality
- `test_chess.py`: Test suite for verifying functionality

## Game Rules Implemented

- Complete chess board setup
- Movement rules for all pieces (pawns, rooks, knights, bishops, queens, kings)
- Turn-based gameplay
- Basic check detection
- Win condition detection (simplified)

## Contributing

Feel free to submit issues and enhancement requests.
