#!/usr/bin/env python3

import numpy as np
from PIL import Image
import chess
import os
import time
import random
import argparse
import sys


class BoardRecognizer:
    """
    A class to recognize chess boards from images and convert them to FEN strings.
    Uses Pillow for image processing instead of OpenCV.
    """

    # Define piece templates and colors
    PIECES = {
        "white": [
            "P",
            "R",
            "N",
            "B",
            "Q",
            "K",
        ],  # pawn, rook, knight, bishop, queen, king
        "black": ["p", "r", "n", "b", "q", "k"],
    }

    # Color thresholds for square detection
    LIGHT_SQUARE_COLOR = (240, 217, 181)  # RGB for light squares
    DARK_SQUARE_COLOR = (181, 136, 99)  # RGB for dark squares
    COLOR_THRESHOLD = 50  # Threshold for color matching

    def __init__(self):
        """Initialize the board recognizer."""
        # Create tmp directory if it doesn't exist
        if not os.path.exists("tmp"):
            os.makedirs("tmp")

    def recognize_board(self, image_path):
        """
        Recognize a chess board from an image and return the FEN string.

        Args:
            image_path: Path to the image file (supports PNG, JPG, JPEG)

        Returns:
            FEN string representing the board position
        """
        try:
            # Load the image (supports various formats through PIL)
            img = Image.open(image_path).convert('RGB')

            # Resize for consistent processing
            img = img.resize((800, 800))

            # Convert to numpy array for easier processing
            img_array = np.array(img)

            # Detect the chess board grid
            squares = self._detect_board_grid(img_array)

            # Recognize pieces on each square
            board_state = self._recognize_pieces(squares, img_array)

            # Convert board state to FEN
            fen = self._board_state_to_fen(board_state)

            return fen

        except Exception as e:
            print(f"Error recognizing board: {e}")
            return None

    def _detect_board_grid(self, img_array):
        """
        Detect the chess board grid and return the coordinates of each square.

        This is a simplified implementation that assumes the board is perfectly
        aligned and takes up the entire image.

        Args:
            img_array: Numpy array representing the image

        Returns:
            List of square coordinates (top-left, bottom-right)
        """
        height, width = img_array.shape[:2]
        square_size = min(height, width) // 8

        squares = []
        for row in range(8):
            for col in range(8):
                top = row * square_size
                left = col * square_size
                bottom = top + square_size
                right = left + square_size

                squares.append(((left, top), (right, bottom)))

        return squares

    def _recognize_pieces(self, squares, img_array):
        """
        Recognize chess pieces on each square.

        This is a simplified implementation that uses color analysis to determine
        if a piece is present and what color it is. A more robust implementation
        would use machine learning or template matching.

        Args:
            squares: List of square coordinates
            img_array: Numpy array representing the image

        Returns:
            8x8 array representing the board state with piece symbols
        """
        board_state = [[" " for _ in range(8)] for _ in range(8)]

        for idx, ((left, top), (right, bottom)) in enumerate(squares):
            row = idx // 8
            col = idx % 8

            # Extract the square
            square_img = img_array[top:bottom, left:right]

            # Determine if the square is light or dark
            is_light_square = (row + col) % 2 == 0

            # Analyze the square to detect pieces
            piece = self._detect_piece_in_square(square_img, is_light_square)
            board_state[row][col] = piece

        return board_state

    def _detect_piece_in_square(self, square_img, is_light_square):
        """
        Detect if there's a piece in the square and determine its type.

        This implementation uses color analysis and edge detection to identify pieces.
        It's been improved to work better with standard chess board images.

        Args:
            square_img: Numpy array representing the square
            is_light_square: Boolean indicating if the square is light-colored

        Returns:
            Piece symbol or empty space
        """
        # Calculate the average color in the center of the square
        height, width = square_img.shape[:2]
        center_region = square_img[
            height // 4 : 3 * height // 4, width // 4 : 3 * width // 4
        ]
        avg_color = np.mean(center_region, axis=(0, 1))

        # Check if the square is empty by comparing with expected square colors
        if is_light_square:
            expected_color = self.LIGHT_SQUARE_COLOR
        else:
            expected_color = self.DARK_SQUARE_COLOR

        color_diff = np.sum(np.abs(avg_color[:3] - expected_color))

        # Calculate color variance in the center region (pieces have more variance)
        color_variance = np.std(center_region, axis=(0, 1)).mean()

        # Check for edges in the center region (pieces have more edges)
        # Simple edge detection using gradient magnitude
        gray_center = np.mean(center_region, axis=2)  # Convert to grayscale
        h_gradient = np.abs(np.diff(gray_center, axis=1))
        v_gradient = np.abs(np.diff(gray_center, axis=0))
        edge_magnitude = np.mean(h_gradient) + np.mean(v_gradient)

        # If color difference is small and variance is low, square is likely empty
        if color_diff < self.COLOR_THRESHOLD and color_variance < 20 and edge_magnitude < 10:
            return " "

        # Determine if the piece is white or black based on brightness
        brightness = np.mean(avg_color[:3])

        # Improved piece type detection based on color patterns and shape features
        # This is still a simplified approach but better than random assignment

        if brightness > 180:  # Likely white piece
            # Check for specific piece features
            if color_variance > 50:  # Complex pieces like knights or queens have higher variance
                if edge_magnitude > 30:
                    return "Q"  # Queen has complex edges
                else:
                    return "N"  # Knight has complex shape but smoother edges
            elif edge_magnitude > 25:
                return "R"  # Rook has distinct edges
            elif edge_magnitude > 20:
                return "B"  # Bishop has medium edges
            elif edge_magnitude > 15:
                return "K"  # King has a crown with some edges
            else:
                return "P"  # Pawn is simplest
        else:  # Likely black piece
            if color_variance > 50:
                if edge_magnitude > 30:
                    return "q"
                else:
                    return "n"
            elif edge_magnitude > 25:
                return "r"
            elif edge_magnitude > 20:
                return "b"
            elif edge_magnitude > 15:
                return "k"
            else:
                return "p"

    def _board_state_to_fen(self, board_state):
        """
        Convert the board state to a FEN string.

        Args:
            board_state: 8x8 array representing the board state with piece symbols

        Returns:
            FEN string
        """
        fen_parts = []

        # Process the board position
        for row in board_state:
            empty_count = 0
            row_fen = ""

            for piece in row:
                if piece == " ":
                    empty_count += 1
                else:
                    if empty_count > 0:
                        row_fen += str(empty_count)
                        empty_count = 0
                    row_fen += piece

            if empty_count > 0:
                row_fen += str(empty_count)

            fen_parts.append(row_fen)

        # Join the rows with slashes
        position = "/".join(fen_parts)

        # Add the rest of the FEN components (active color, castling, etc.)
        # For simplicity, we'll assume it's white's turn and all castling is available
        fen = f"{position} w KQkq - 0 1"

        return fen

    def validate_fen(self, fen):
        """
        Validate a FEN string by trying to create a chess.Board with it.

        Args:
            fen: FEN string to validate

        Returns:
            Boolean indicating if the FEN is valid
        """
        try:
            chess.Board(fen)
            return True
        except ValueError:
            return False

    def save_board_image(self, fen):
        """
        Generate and save an image of a board from a FEN string.

        Args:
            fen: FEN string representing the board position

        Returns:
            Path to the saved image
        """
        try:
            board = chess.Board(fen)

            # Use the chess.svg module to generate an SVG
            import chess.svg
            import cairosvg

            # Generate a unique filename
            timestamp = int(time.time())
            random_suffix = random.randint(1000, 9999)
            filename = f"recognized_board_{timestamp}_{random_suffix}.png"
            filepath = os.path.join("tmp", filename)

            # Generate SVG and convert to PNG
            svg_content = chess.svg.board(board=board, size=400, coordinates=True)
            png_bytes = cairosvg.svg2png(bytestring=svg_content.encode("utf-8"))

            # Save to file
            with open(filepath, "wb") as f:
                f.write(png_bytes)

            return filepath

        except Exception as e:
            print(f"Error saving board image: {e}")
            return None


def main():
    """Command-line interface for the BoardRecognizer."""
    parser = argparse.ArgumentParser(description="Convert chess board images to FEN strings")
    parser.add_argument("image_path", help="Path to the chess board image")
    parser.add_argument("--save", action="store_true", help="Save the recognized board as an image")
    parser.add_argument("--output", help="Output directory for saved images", default="tmp")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode with detailed output")
    parser.add_argument("--turn", choices=["w", "b"], default="w", help="Specify whose turn it is (w=white, b=black)")
    parser.add_argument("--castling", default="KQkq", help="Castling availability (e.g., 'KQkq', 'Kk', '-')")

    args = parser.parse_args()

    # Check if the image file exists
    if not os.path.exists(args.image_path):
        print(f"Error: Image file '{args.image_path}' not found")
        return 1

    # Create the output directory if it doesn't exist
    if args.save and not os.path.exists(args.output):
        os.makedirs(args.output)

    # Create a BoardRecognizer instance
    recognizer = BoardRecognizer()

    # Recognize the board
    print(f"Processing image: {args.image_path}")
    fen = recognizer.recognize_board(args.image_path)

    if fen:
        # Replace the default turn and castling with user-specified values
        fen_parts = fen.split(" ")
        fen_parts[1] = args.turn  # Set the turn
        fen_parts[2] = args.castling  # Set castling availability
        fen = " ".join(fen_parts)

        print(f"Recognized FEN: {fen}")

        # Validate the FEN
        if recognizer.validate_fen(fen):
            print("FEN validation: Valid")

            # Save the board image if requested
            if args.save:
                board_image_path = recognizer.save_board_image(fen)
                if board_image_path:
                    print(f"Board image saved to: {board_image_path}")
                else:
                    print("Error: Failed to save board image")

            # Print command to create a game with this FEN
            print("\nTo create a game with this position, use:")
            print(f"/fengame {fen} white")
            print("or")
            print(f"/fengame {fen} black")
        else:
            print("FEN validation: Invalid")
    else:
        print("Error: Failed to recognize board")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
