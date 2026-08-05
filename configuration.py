import os

# App version (major.minor.patch). Bump the patch (last digit) on every deploy.
APP_VERSION = "1.1.2"

# Ensure data directory exists
data_dir = "data"
if not os.path.exists(data_dir):
    os.makedirs(data_dir)

# Store database in the data directory for persistence
GAMES_DB = os.path.join(data_dir, "games.db")
