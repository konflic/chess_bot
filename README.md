# Telegram Chess Bot

A multiplayer chess game for Telegram with real-time gameplay, database storage, and multilingual support.

## Features

- Multiplayer chess games over Telegram
- Invite links for joining games
- Real-time notifications when it's your turn
- Support for standard chess notation moves
- SQLite database for storing game states
- Automatic cleanup of finished games
- Multilingual support (English and Russian)
- Automatic language detection based on user's Telegram settings
- Command menu in Telegram interface for easy navigation
- Keyboard shortcuts for common commands

## Requirements

- Python 3.7+
- Dependencies listed in `requirements.txt`

## Setup

1. Install the required packages:
```bash
pip install -r requirements.txt
```

2. Obtain a Telegram bot token from [@BotFather](https://t.me/BotFather) on Telegram

3. Replace `YOUR_BOT_TOKEN_HERE` in the `TOKEN` file with your actual bot token

4. Run the bot:
```bash
python bot.py
```

## Usage

- `/start` - Display welcome message and instructions
- `/newgame` - Create a new chess game and get an invite link
- `/join [link]` - Join a game using an invite link
- Move format: Type moves in algebraic notation (e.g., `e2e4`, `Nf3`, `O-O`)

## How to Play

1. Player 1 creates a game using `/newgame`
2. Player 1 shares the generated invite link with Player 2
3. Player 2 joins the game using `/join [link]`
4. Players take turns making moves in algebraic notation
5. The bot sends notifications to players when it's their turn
6. The game ends when there's a checkmate or draw

## Technical Details

- Chess engine powered by `python-chess` library
- SQLite database stores active games and move history
- Games are automatically removed from database when finished
- Each game has a unique invite link that becomes invalid after use
- Language support automatically detects user's language from Telegram settings
- All messages are translated based on user's preferred language
- Command menu appears in Telegram's menu button for easy access
- Keyboard shortcuts provide quick access to common commands
