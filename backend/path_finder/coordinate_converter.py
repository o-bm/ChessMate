"""
Coordinate Converter

This module converts between chess board coordinates (a1-h8) and the physical
17x19 grid system used by the robotic chess board.

Grid System Explanation:
- Standard chess board: 8x8 squares
- Physical grid: 17x19 points (square centers + edges + discard areas)
- Each square has a center point and edge points
- Pieces move along edges to avoid collisions
- Grid coordinates: (0,0) at bottom-left corner, (16,18) at top-right corner
- Discard areas: y=0 (white pieces), y=18 (black pieces)
- Chess squares offset by +1 in y-direction to accommodate bottom discard area
"""

import logging

logger = logging.getLogger(__name__)


class CoordinateConverter:
    """
    Converts between chess notation and 17x19 grid coordinates.
    
    The 17x19 grid maps as follows:
    - a1 square center: (1, 2)  # +1 offset for discard area
    - Arduino home position: (0, 0) <- bottom-left corner
    - h8 square center: (15, 16) # +1 offset for discard area
    - White discard area: y=0
    - Black discard area: y=18
    
    Each chess square is 2x2 grid units, with centers at odd x, even y coordinates.
    """
    
    def __init__(self):
        """Initialize the coordinate converter."""
        # Chess files (a-h) map to grid x-coordinates
        self.files = 'abcdefgh'
        # Chess ranks (1-8) map to grid y-coordinates
        self.ranks = '12345678'
        
        # Grid dimensions - expanded to 17x19 for discard areas
        self.grid_width = 17
        self.grid_height = 19
        self.square_size = 2  # Each chess square spans 2x2 grid units
        
        # Discard areas
        self.white_discard_y = 0   # Bottom discard area (y=0)
        self.black_discard_y = 18  # Top discard area (y=18)
        
        # Track captured piece positions
        self.white_captured_pieces = []  # List of x-coordinates
        self.black_captured_pieces = []  # List of x-coordinates
    
    def chess_to_grid(self, square: str, use_channel: bool = True) -> dict:
        """
        Convert chess square notation to grid coordinates.
        
        Args:
            square: Chess square in algebraic notation (e.g., 'e4', 'a1')
            use_channel: If True, return channel position (between squares for movement)
                        If False, return square center (for piece pickup/placement)
        
        Returns:
            dict: Grid coordinates {"x": int, "y": int}
        
        Example:
            chess_to_grid('e4', use_channel=True) -> {"x": 8, "y": 7}   # Channel position
            chess_to_grid('e4', use_channel=False) -> {"x": 9, "y": 8}  # Square center
        """
        if len(square) != 2:
            raise ValueError(f"Invalid square notation: {square}")
        
        file_char = square[0].lower()
        rank_char = square[1]
        
        if file_char not in self.files or rank_char not in self.ranks:
            raise ValueError(f"Invalid square notation: {square}")
        
        # Convert to 0-based indices
        file_index = self.files.index(file_char)  # 0-7 for a-h
        rank_index = self.ranks.index(rank_char)  # 0-7 for 1-8
        
        if use_channel:
            # Channel positions - robot travels between squares
            # Channels are at even x, odd y coordinates
            grid_x = file_index * self.square_size  # 0, 2, 4, 6, 8, 10, 12, 14
            grid_y = (rank_index * self.square_size) + 1  # 1, 3, 5, 7, 9, 11, 13, 15
        else:
            # Square centers - for piece pickup/placement only
            # Centers at odd x, even y coordinates
            grid_x = (file_index * self.square_size) + 1  # 1, 3, 5, 7, 9, 11, 13, 15
            grid_y = (rank_index * self.square_size) + 2  # 2, 4, 6, 8, 10, 12, 14, 16
        
        result = {"x": grid_x, "y": grid_y}
        position_type = "channel" if use_channel else "center"
        logger.debug(f"Converted {square} to {position_type} coordinates: {result}")
        return result
    
    def grid_to_chess(self, x: int, y: int) -> str:
        """
        Convert 17x19 grid coordinates to chess square notation.
        
        Args:
            x: Grid x-coordinate (0-16)
            y: Grid y-coordinate (0-16)
        
        Returns:
            str: Chess square notation (e.g., "e4")
        
        Note: This assumes the coordinates represent a square center.
        """
        if not (0 <= x <= 16) or not (0 <= y <= 18):
            raise ValueError(f"Grid coordinates out of range: ({x}, {y})")
        
        # Convert grid coordinates back to chess indices
        # Subtract 1 to get to corner, then divide by 2
        # Account for discard area offset
        file_index = (x - 1) // self.square_size
        rank_index = (y - 2) // self.square_size  # -2 for discard offset
        
        if not (0 <= file_index <= 7) or not (0 <= rank_index <= 7):
            raise ValueError(f"Grid coordinates don't map to valid chess square: ({x}, {y})")
        
        file_char = self.files[file_index]
        rank_char = str(rank_index + 1)
        
        square = file_char + rank_char
        logger.debug(f"Grid coordinates ({x}, {y}) -> Chess square {square}")
        
        return square
    
    def get_square_corners(self, square: str) -> dict:
        """
        Get all four corner coordinates of a chess square.
        
        Args:
            square: Chess square notation (e.g., "e4")
        
        Returns:
            dict: Corner coordinates with keys "bottom_left", "bottom_right", 
                  "top_left", "top_right"
        """
        center = self.chess_to_grid(square)
        
        corners = {
            "bottom_left": {"x": center["x"] - 1, "y": center["y"] - 1},
            "bottom_right": {"x": center["x"] + 1, "y": center["y"] - 1},
            "top_left": {"x": center["x"] - 1, "y": center["y"] + 1},
            "top_right": {"x": center["x"] + 1, "y": center["y"] + 1}
        }
        
        logger.debug(f"Square {square} corners: {corners}")
        return corners
    
    def get_edge_points(self, square: str) -> dict:
        """
        Get the edge midpoints of a chess square (for piece movement).
        
        Args:
            square: Chess square notation (e.g., "e4")
        
        Returns:
            dict: Edge midpoints with keys "left", "right", "bottom", "top"
        """
        center = self.chess_to_grid(square)
        
        edges = {
            "left": {"x": center["x"] - 1, "y": center["y"]},
            "right": {"x": center["x"] + 1, "y": center["y"]},
            "bottom": {"x": center["x"], "y": center["y"] - 1},
            "top": {"x": center["x"], "y": center["y"] + 1}
        }
        
        logger.debug(f"Square {square} edges: {edges}")
        return edges
    
    def distance_between_squares(self, from_square: str, to_square: str) -> dict:
        """
        Calculate the grid distance between two chess squares.
        
        Args:
            from_square: Starting square (e.g., "e2")
            to_square: Ending square (e.g., "e4")
        
        Returns:
            dict: {"x": int, "y": int, "manhattan": int} distances
        """
        from_coords = self.chess_to_grid(from_square)
        to_coords = self.chess_to_grid(to_square)
        
        dx = to_coords["x"] - from_coords["x"]
        dy = to_coords["y"] - from_coords["y"]
        manhattan = abs(dx) + abs(dy)
        
        result = {"x": dx, "y": dy, "manhattan": manhattan}
        logger.debug(f"Distance {from_square} -> {to_square}: {result}")
        
        return result
    
    def get_home_position(self) -> dict:
        """
        Get the Arduino home position coordinates.
        
        Returns:
            dict: {"x": 0, "y": 0} - bottom-left corner of the board
        """
        return {"x": 0, "y": 0}
    
    def is_valid_grid_position(self, x: int, y: int) -> bool:
        """
        Check if grid coordinates are within the valid 17x19 range.
        
        Args:
            x: Grid x-coordinate
            y: Grid y-coordinate
        
        Returns:
            bool: True if valid, False otherwise
        """
        return 0 <= x <= 16 and 0 <= y <= 18
    
    def get_next_discard_position(self, is_white_capture: bool) -> dict:
        """
        Get the next available position in the discard area for a captured piece.
        
        Args:
            is_white_capture: True if white is capturing (piece goes to black discard),
                             False if black is capturing (piece goes to white discard)
        
        Returns:
            dict: {"x": int, "y": int} coordinates for the captured piece
        """
        if is_white_capture:
            # White captures black piece -> goes to black discard area (top)
            discard_y = self.black_discard_y
            captured_list = self.black_captured_pieces
        else:
            # Black captures white piece -> goes to white discard area (bottom)
            discard_y = self.white_discard_y
            captured_list = self.white_captured_pieces
        
        # Find next available x-coordinate
        if not captured_list:
            # First capture - start at x=1
            next_x = 1
        else:
            # Place next to the last captured piece
            next_x = max(captured_list) + 2  # +2 to leave space between pieces
            
            # If we've reached the edge, wrap to next row (not implemented yet)
            if next_x > 15:
                next_x = 1  # Reset to start for now
        
        # Record this position
        captured_list.append(next_x)
        
        position = {"x": next_x, "y": discard_y}
        logger.debug(f"Next discard position ({'white' if is_white_capture else 'black'} capture): {position}")
        
        return position
    
    def is_capture_move(self, from_square: str, to_square: str, board_state: dict = None) -> bool:
        """
        Determine if a move is a capture based on board state.
        
        Args:
            from_square: Starting square
            to_square: Destination square
            board_state: Optional board state dict with piece positions
        
        Returns:
            bool: True if this is a capture move
        
        Note: If no board_state is provided, this returns False.
              In a real implementation, you'd pass the current board state.
        """
        if board_state is None:
            return False
        
        # Check if destination square is occupied by opponent piece
        return to_square in board_state and board_state[to_square] is not None
    
    def reset_discard_tracking(self):
        """Reset the discard pile tracking (for new games)."""
        self.white_captured_pieces = []
        self.black_captured_pieces = []
        logger.info("Discard pile tracking reset")


# Example usage and testing
if __name__ == "__main__":
    # Set up logging for testing
    logging.basicConfig(level=logging.DEBUG)
    
    converter = CoordinateConverter()
    
    # Test square conversions
    test_squares = ["a1", "e4", "h8", "d5", "a8", "h1"]
    
    print("Testing coordinate conversions:")
    for square in test_squares:
        try:
            grid_coords = converter.chess_to_grid(square)
            back_to_chess = converter.grid_to_chess(grid_coords["x"], grid_coords["y"])
            print(f"  {square} -> {grid_coords} -> {back_to_chess}")
        except Exception as e:
            print(f"  {square} -> ERROR: {e}")
    
    # Test distance calculations
    print("\nTesting distance calculations:")
    test_moves = [("e2", "e4"), ("a1", "h8"), ("d4", "d4"), ("a1", "a2")]
    for from_sq, to_sq in test_moves:
        distance = converter.distance_between_squares(from_sq, to_sq)
        print(f"  {from_sq} -> {to_sq}: {distance}")
    
    # Test corner and edge calculations
    print(f"\nSquare e4 corners: {converter.get_square_corners('e4')}")
    print(f"Square e4 edges: {converter.get_edge_points('e4')}")
    print(f"Home position: {converter.get_home_position()}")
