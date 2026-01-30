from languages import LanguageManager
import os

# Bot configuration
BOT_NAME = "chezz_game_bot"
BOT_VERSION = "1.0.1"

# Ensure data directory exists
data_dir = "data"
if not os.path.exists(data_dir):
    os.makedirs(data_dir)

# Store database in the data directory for persistence
GAMES_DB = os.path.join(data_dir, "games.db")

# Create a global language manager instance
language_manager = LanguageManager()
