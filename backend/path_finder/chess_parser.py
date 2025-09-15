"""
Chess Notation Parser

This module handles parsing of chess moves in algebraic notation.
Supports standard moves like "e2e4", "Nf3", "O-O", etc.
"""

import re
import logging

logger = logging.getLogger(__name__)


class ChessNotationParser:
    """
    Parser for chess algebraic notation.
    
    Handles various forms of chess notation:
    - Simple moves: e2e4, a7a5
    - Piece moves: Nf3, Bb5
    - Captures: exd5, Nxf7
    - Castling: O-O, O-O-O
    - Promotions: e8=Q
    """
    
    def __init__(self):
        """Initialize the chess notation parser."""
        # Chess board files (columns) and ranks (rows)
        self.files = 'abcdefgh'
        self.ranks = '12345678'
        
        # Regular expressions for different move types
        self.patterns = {
            # Simple coordinate moves: e2e4, a7a5
            'coordinate': re.compile(r'^([a-h][1-8])([a-h][1-8])$'),
            
            # Standard algebraic notation: Nf3, Be5, Qh4
            'standard': re.compile(r'^([NBRQK]?)([a-h]?[1-8]?)x?([a-h][1-8])(\+|#)?$'),
            
            # Captures: exd5, Nxf7
            'capture': re.compile(r'^([a-h][1-8])x([a-h][1-8])(\+|#)?$'),

            # Castling moves
            'castling': re.compile(r'^(O-O-O|O-O)(\+|#)?$'),
            
            # Pawn promotion: e8=Q
            'promotion': re.compile(r'^([a-h])([18])=([NBRQ])(\+|#)?$')
        }
    
    def parse_move(self, move_str: str) -> tuple:
        """
        Parse a chess move string and return from/to squares.
        
        Args:
            move_str: Chess move in algebraic notation (e.g., "e2e4", "Nf3")
        
        Returns:
            tuple: (from_square, to_square) as strings (e.g., ("e2", "e4"))
        
        Raises:
            ValueError: If the move cannot be parsed
        """
        move_str = move_str.strip()
        logger.debug(f"Parsing chess move: {move_str}")
        
        # Try coordinate notation first (e.g., e2e4)
        match = self.patterns['coordinate'].match(move_str)
        if match:
            from_square = match.group(1)
            to_square = match.group(2)
            logger.debug(f"Parsed coordinate move: {from_square} -> {to_square}")
            return from_square, to_square
        
        # Try castling moves
        match = self.patterns['castling'].match(move_str)
        if match:
            castling_type = match.group(1)
            return self._parse_castling(castling_type)
        
        # Try standard algebraic notation (this is more complex and would need board state)
        match = self.patterns['standard'].match(move_str)
        if match:
            # For now, we'll raise an error since we need board state to resolve ambiguity
            raise ValueError(f"Standard algebraic notation '{move_str}' requires board state to resolve. Please use coordinate notation (e.g., 'e2e4')")
        
        # Try pawn promotion
        match = self.patterns['promotion'].match(move_str)
        if match:
            file = match.group(1)
            rank = match.group(2)
            to_square = f"{file}{rank}"
            # Assume pawn came from the previous rank
            from_rank = '7' if rank == '8' else '2'
            from_square = f"{file}{from_rank}"
            logger.debug(f"Parsed promotion move: {from_square} -> {to_square}")
            return from_square, to_square
        
        raise ValueError(f"Unable to parse chess move: {move_str}")
    
    def _parse_castling(self, castling_type: str) -> tuple:
        """
        Parse castling moves and return king movement.
        
        Args:
            castling_type: "O-O" for kingside, "O-O-O" for queenside
        
        Returns:
            tuple: (from_square, to_square) for the king movement
        """
        if castling_type == "O-O":  # Kingside castling
            # Assume white castling for now (would need game state for color)
            logger.debug("Parsed kingside castling: e1 -> g1")
            return "e1", "g1"
        elif castling_type == "O-O-O":  # Queenside castling
            logger.debug("Parsed queenside castling: e1 -> c1")
            return "e1", "c1"
        else:
            raise ValueError(f"Invalid castling notation: {castling_type}")
    
    def is_valid_square(self, square: str) -> bool:
        """
        Check if a square notation is valid.
        
        Args:
            square: Square notation (e.g., "e4")
        
        Returns:
            bool: True if valid, False otherwise
        """
        if len(square) != 2:
            return False
        
        file, rank = square[0], square[1]
        return file in self.files and rank in self.ranks
    
    def square_to_coords(self, square: str) -> tuple:
        """
        Convert square notation to 0-based coordinates.
        
        Args:
            square: Square notation (e.g., "e4")
        
        Returns:
            tuple: (file_index, rank_index) where a1 = (0, 0)
        """
        if not self.is_valid_square(square):
            raise ValueError(f"Invalid square: {square}")
        
        file_index = self.files.index(square[0])
        rank_index = int(square[1]) - 1
        
        return file_index, rank_index


# Example usage and testing
if __name__ == "__main__":
    # Set up logging for testing
    logging.basicConfig(level=logging.DEBUG)
    
    parser = ChessNotationParser()
    
    # Test various move types
    test_moves = [
        "e2e4",    # Pawn move
        "g1f3",    # Knight move
        "a7a5",    # Pawn move
        "h1h8",    # Rook move across board
        "O-O",     # Kingside castling
        "O-O-O",   # Queenside castling
    ]
    
    print("Testing chess notation parser:")
    for move in test_moves:
        try:
            from_sq, to_sq = parser.parse_move(move)
            print(f"  {move} -> {from_sq} to {to_sq}")
        except Exception as e:
            print(f"  {move} -> ERROR: {e}")
