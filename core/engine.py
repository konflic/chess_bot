import random
import chess


class ComputerEngine:
    @staticmethod
    def get_move(board):
        capturing_moves = []
        for move in board.legal_moves:
            if board.is_capture(move):
                capturing_moves.append(move)

        if capturing_moves:
            return random.choice(capturing_moves)

        legal_moves = list(board.legal_moves)
        if not legal_moves:
            return None
        return random.choice(legal_moves)
