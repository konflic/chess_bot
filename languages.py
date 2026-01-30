#!/usr/bin/env python3

# Dictionary of translations for all user-facing messages
TRANSLATIONS = {
    "en": {
        # Welcome messages
        "welcome_title": "Welcome to CheZZ!",
        "welcome_commands": "Commands",
        "welcome_newgame": "/newgame - Start a new game",
        "welcome_current_game": "/current_game - Show your current game",
        "welcome_help": "/help - Show all available commands",
        "welcome_intro": "Welcome to CheZZ! Play chess with your friends right here in Telegram.",
        "welcome_quick_start": "Quick Start:",
        "welcome_leave": "/surrender - Surrender current game (forfeit)",
        "welcome_how_to_play": "How to play",
        "welcome_move_format": "Just type moves like e2e4, Nf3, or O-O",
        # Game creation and joining
        "new_game_created": "New chess game created!",
        "existing_waiting_game": "You already have a waiting game!",
        "game_id": "Game ID",
        "invite_code": "Invite code",
        "share_link": "Share this link to invite a friend",
        "or_they_can_use": "Or they can use",
        "already_in_game": "You're already in an active game!",
        "use_current_game": "Use /current_game to see details",
        "or_leave": "or /surrender to surrender the game.",
        "invalid_invite": "Invalid or expired invite link!",
        "invalid_reasons": "Possible reasons",
        "game_has_players": "• Game already has 2 players",
        "game_not_exist": "• Game doesn't exist",
        "link_expired": "• Link is expired",
        "create_own_game": "Create your own game with /newgame",
        # Game status
        "joined_success": "Successfully joined game!",
        "you_are": "You are",
        "white": "White 🌝",
        "black": "Black 🌚",
        "your_turn": "Its your turn!",
        "waiting_opponent": "Waiting for opponent to move...",
        "has_joined": "has joined game!",
        "player_joined": "Player has joined your game!",
        "not_in_active_game": "You're not in an active game. Start one with /newgame",
        "no_active_games": "You don't have any active games. Start one with /newgame",
        # Game play
        "current_active_game": "Current Active Game",
        "opponent": "Opponent",
        "started_at": "Started at",
        "move": "Move",
        "current_turn": "Current turn",
        "opponent_played": "Opponent played",
        "your_turn_exclamation": "Your turn!",
        "invalid_move": "Invalid move:",
        # Board command
        "board_command": "Use /board to see the current board",
        "no_active_board": "You don't have an active game to show the board for",
        # Ping command
        "ping_sent": "Reminder sent to your opponent",
        "ping_received": "Your opponent is waiting for your move",
        "ping_cooldown": "You can only send a reminder once every 30 minutes",
        "ping_not_opponent_turn": "It's your turn to move, not your opponent's",
        "ping_no_game": "You don't have an active game to send a reminder for",
        # Game end
        "game_ended": "Game ended.",
        "left_game": "You have left game",
        "opponent_wins": "Your opponent wins by forfeit.",
        "start_new_game": "Start a new game anytime with",
        "victory_forfeit": "Victory by forfeit!",
        "player_left": "Player has left game",
        "awarded_win": "You are awarded the win! 🎉",
        "confirm_surrender": "Are you sure you want to surrender this game? Your opponent will win. Reply with /confirm_surrender to confirm or /cancel to continue playing.",
        "surrender_cancelled": "Surrender cancelled. The game continues!",
        "active_games": "Your active games:",
        "game_details": "Game ID: %s | Opponent: %s | You play as: %s\nTurn: %s",
        "game_set_active": "Game %s is now your active game.",
        "checkmate_win": "Checkmate! You win!",
        "checkmate_lose": "Checkmate! You lose!",
        "game_draw": "Game ended in a draw!",
        "no_active_game": "No active game found.",
        "existing_game_error": "You already have an active game with this player!",
        "check_active_games": "Check your active games with",
        "select_game_to_surrender": "Select a game to surrender:",
        "surrender_game": "Surrender game",
        # Help command
        "help_title": "CheZZ Bot Help",
        "help_game_commands": "Game Commands",
        "help_newgame": "Create a new chess game",
        "help_current_game": "Show your current active game",
        "help_active_games": "List all your active games",
        "help_board": "Display the current board state",
        "help_interaction_commands": "Interaction Commands",
        "help_ping": "Remind opponent it's their turn",
        "help_surrender": "Surrender the current game",
        "help_how_to_play": "How to Play",
        "help_move_format": "Simply type your moves in standard algebraic notation:",
        "help_examples": "Examples",
        "help_example_pawn": "Move pawn from e2 to e4",
        "help_example_knight": "Move knight to f3",
        "help_example_castle": "Castle kingside",
        "help_example_capture": "Queen captures on f7",
    },
    "ru": {
        # Welcome messages
        "welcome_title": "Добро пожаловать в CheZZ!",
        "welcome_commands": "Команды",
        "welcome_newgame": "/newgame - Начать новую игру",
        "welcome_current_game": "/current_game - Показать текущую игру",
        "welcome_help": "/help - Показать все доступные команды",
        "welcome_intro": "Добро пожаловать в CheZZ! Играйте в шахматы с друзьями прямо в Telegram.",
        "welcome_quick_start": "Быстрый старт:",
        "welcome_leave": "/surrender - Сдаться в текущей игре",
        "welcome_how_to_play": "Как играть",
        "welcome_move_format": "Просто введите ходы, например e2e4, Nf3 или O-O",
        # Game creation and joining
        "new_game_created": "Новая шахматная игра создана!",
        "existing_waiting_game": "У вас уже есть ожидающая игра!",
        "game_id": "ID игры",
        "invite_code": "Код приглашения",
        "share_link": "Поделитесь этой ссылкой, чтобы пригласить друга",
        "or_they_can_use": "Или они могут использовать",
        "already_in_game": "Вы уже участвуете в активной игре!",
        "use_current_game": "Используйте /current_game, чтобы увидеть детали",
        "or_leave": "или /surrender, чтобы сдаться.",
        "invalid_invite": "Недействительная или просроченная ссылка приглашения!",
        "invalid_reasons": "Возможные причины",
        "game_has_players": "• В игре уже есть 2 игрока",
        "game_not_exist": "• Игра не существует",
        "link_expired": "• Срок действия ссылки истек",
        "create_own_game": "Создайте свою игру с помощью /newgame",
        # Game status
        "joined_success": "Успешно присоединились к игре!",
        "you_are": "Вы играете",
        "white": "Белыми 🌝",
        "black": "Черными 🌚",
        "your_turn": "Ваш ход!",
        "waiting_opponent": "Ожидание хода соперника...",
        "has_joined": "присоединился к игре!",
        "player_joined": "Игрок присоединился к вашей игре!",
        "not_in_active_game": "Вы не участвуете в активной игре. Начните с /newgame",
        "no_active_games": "У вас нет активных игр. Начните с /newgame",
        # Game play
        "current_active_game": "Текущая активная игра",
        "opponent": "Соперник",
        "started_at": "Начата в",
        "move": "Ход",
        "current_turn": "Текущий ход",
        "opponent_played": "Соперник сделал ход",
        "your_turn_exclamation": "Ваш ход!",
        "invalid_move": "Недопустимый ход:",
        # Board command
        "board_command": "Используйте /board чтобы увидеть текущую доску",
        "no_active_board": "У вас нет активной игры, чтобы показать доску",
        # Ping command
        "ping_sent": "Напоминание отправлено вашему сопернику",
        "ping_received": "Ваш соперник ожидает вашего хода",
        "ping_cooldown": "Вы можете отправлять напоминание только раз в 30 минут",
        "ping_not_opponent_turn": "Сейчас ваш ход, а не вашего соперника",
        "ping_no_game": "У вас нет активной игры, чтобы отправить напоминание",
        # Game end
        "game_ended": "Игра окончена.",
        "left_game": "Вы покинули игру",
        "opponent_wins": "Ваш соперник выигрывает из-за вашего отказа.",
        "start_new_game": "Начните новую игру в любое время с помощью",
        "victory_forfeit": "Победа из-за отказа соперника!",
        "player_left": "Игрок покинул игру",
        "awarded_win": "Вам присуждена победа! 🎉",
        "confirm_surrender": "Вы уверены, что хотите сдаться? Ваш соперник победит. Ответьте /confirm_surrender для подтверждения или /cancel для продолжения игры.",
        "surrender_cancelled": "Сдача отменена. Игра продолжается!",
        "active_games": "Ваши активные игры:",
        "game_details": "ID игры: %s | Соперник: %s | Вы играете: %s\nХод: %s",
        "set_active_game": "Сделать активной игрой",
        "game_set_active": "Игра %s теперь ваша активная игра.",
        "checkmate_win": "Шах и мат! Вы выиграли!",
        "checkmate_lose": "Шах и мат! Вы проиграли!",
        "game_draw": "Игра закончилась вничью!",
        "no_active_game": "Активная игра не найдена.",
        "existing_game_error": "У вас уже есть активная игра с этим игроком!",
        "check_active_games": "Проверьте ваши активные игры с помощью",
        "select_game_to_surrender": "Выберите игру для сдачи:",
        "surrender_game": "Сдаться в игре",
        # Help command
        "help_title": "Справка по боту CheZZ",
        "help_game_commands": "Команды игры",
        "help_newgame": "Создать новую шахматную игру",
        "help_current_game": "Показать вашу текущую активную игру",
        "help_active_games": "Список всех ваших активных игр",
        "help_board": "Отобразить текущее состояние доски",
        "help_interaction_commands": "Команды взаимодействия",
        "help_ping": "Напомнить сопернику о его ходе",
        "help_surrender": "Сдаться в текущей игре",
        "help_how_to_play": "Как играть",
        "help_move_format": "Просто вводите ходы в стандартной алгебраической нотации:",
        "help_examples": "Примеры",
        "help_example_pawn": "Переместить пешку с e2 на e4",
        "help_example_knight": "Переместить коня на f3",
        "help_example_castle": "Рокировка в короткую сторону",
        "help_example_capture": "Ферзь берет на f7",
        "command_menu_hint": "Напишите / чтобы увидеть все доступные команды в меню команд",
    },
}


class LanguageManager:
    def __init__(self):
        self.default_language = "en"
        self.user_languages = {}  # Store user language preferences: {user_id: language_code}

    def get_user_language(self, user_id, language_code=None):
        """
        Get the user's preferred language.
        If language_code is provided, it will be used to update the user's preference.
        Otherwise, returns the stored preference or default language.
        """
        if language_code:
            # Update user's language preference if a specific language is provided
            if language_code.startswith("ru"):
                self.user_languages[user_id] = "ru"
            else:
                self.user_languages[user_id] = "en"

        # Return the user's stored language preference or default
        return self.user_languages.get(user_id, self.default_language)

    def get_message(self, key, user_id, language_code=None):
        """
        Get a translated message for the given key and user.
        """
        lang = self.get_user_language(user_id, language_code)

        # Fallback to English if the key doesn't exist in the user's language
        if key not in TRANSLATIONS[lang]:
            lang = "en"

        return TRANSLATIONS[lang].get(key, f"Missing translation: {key}")
