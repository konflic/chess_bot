from languages import LanguageManager
import os

BOT_NAME = "chezz_game_bot"

# Ensure data directory exists
data_dir = "data"
if not os.path.exists(data_dir):
    os.makedirs(data_dir)

# Store database in the data directory for persistence
GAMES_DB = os.path.join(data_dir, "games.db")

# Create a global language manager instance
language_manager = LanguageManager()
