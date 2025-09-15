from coordinate_converter import CoordinateConverter

class PathPlanner:
    def __init__(self):
        self.converter = CoordinateConverter()
        self.home_position = self.converter.get_home_position()
    
    def plan_path(self, from_square: str, to_square: str, is_capture: bool = False, 
                  is_white_move: bool = True, board_state: dict = None) -> list:
        if self._is_castling_move(from_square, to_square):
            return self._plan_castling_path(from_square, to_square, is_white_move)
        
        from_coords = self.converter.chess_to_grid(from_square, use_channel=False)
        to_coords = self.converter.chess_to_grid(to_square, use_channel=False)
        
        path = ["lower", "home"]
        
        if is_capture:
            path.extend(self._plan_edge_movement(self.home_position, to_coords, False))
            path.append("raise")
            discard_pos = {"x": 1, "y": 0}
            path.extend(self._plan_discard_movement(to_coords, discard_pos))
            path.append(f"X: 0 Y: -1")  # Move to discard BEFORE lowering
            path.append("lower")
            path.append("home")
        
        path.extend(self._plan_edge_movement(self.home_position, from_coords, False))
        path.append("raise")
        path.extend(self._plan_edge_movement(from_coords, to_coords, True))
        path.append(f"X: 1 Y: 1")  # MOVE TO FINAL POSITION FIRST
        path.append("lower")       # THEN LOWER
        
        return path
    
    def _plan_discard_movement(self, from_pos: dict, discard_pos: dict) -> list:
        commands = []
        channel_y = from_pos["y"] - 1 if from_pos["y"] % 2 == 0 else from_pos["y"]
        channel_dy = channel_y - from_pos["y"]
        if channel_dy != 0:
            commands.append(f"X: 0 Y: {channel_dy}")
        dx = discard_pos["x"] - from_pos["x"]
        if dx != 0:
            commands.append(f"X: {dx} Y: 0")
        target_channel_y = 1
        final_dy = target_channel_y - channel_y
        if final_dy != 0:
            commands.append(f"X: 0 Y: {final_dy}")
        return commands
    
    def _plan_edge_movement(self, from_pos: dict, to_pos: dict, carrying_piece: bool = False) -> list:
        dx = to_pos["x"] - from_pos["x"]
        dy = to_pos["y"] - from_pos["y"]
        
        if not carrying_piece:
            if dx != 0 or dy != 0:
                return [f"X: {dx} Y: {dy}"]
        else:
            if abs(dx) >= abs(dy):
                return self._plan_horizontal_edge_movement(from_pos, to_pos, dx, dy)
            else:
                return self._plan_vertical_edge_movement(from_pos, to_pos, dx, dy)
        return []
    
    def _plan_horizontal_edge_movement(self, from_pos: dict, to_pos: dict, dx: int, dy: int) -> list:
        commands = []
        channel_y = from_pos["y"] + 1 if (from_pos["y"] % 2 == 0 and dy >= 0) else from_pos["y"] - 1 if from_pos["y"] % 2 == 0 else from_pos["y"]
        if channel_y % 2 == 0:
            channel_y += 1 if dy >= 0 else -1
        channel_dy = channel_y - from_pos["y"]
        if channel_dy != 0:
            commands.append(f"X: 0 Y: {channel_dy}")
        target_channel_x = to_pos["x"] - 1 if to_pos["x"] % 2 == 1 else to_pos["x"]
        horizontal_dx = target_channel_x - from_pos["x"]
        if horizontal_dx != 0:
            commands.append(f"X: {horizontal_dx} Y: 0")
        target_channel_y = to_pos["y"] - 1 if to_pos["y"] % 2 == 0 else to_pos["y"]
        vertical_dy = target_channel_y - channel_y
        if vertical_dy != 0:
            commands.append(f"X: 0 Y: {vertical_dy}")
        return commands
    
    def _plan_vertical_edge_movement(self, from_pos: dict, to_pos: dict, dx: int, dy: int) -> list:
        commands = []
        channel_x = from_pos["x"] + 1 if (from_pos["x"] % 2 == 1 and dx >= 0) else from_pos["x"] - 1 if from_pos["x"] % 2 == 1 else from_pos["x"]
        if channel_x % 2 == 1:
            channel_x += 1 if dx >= 0 else -1
        channel_dx = channel_x - from_pos["x"]
        if channel_dx != 0:
            commands.append(f"X: {channel_dx} Y: 0")
        target_channel_y = to_pos["y"] - 1 if to_pos["y"] % 2 == 0 else to_pos["y"]
        vertical_dy = target_channel_y - from_pos["y"]
        if vertical_dy != 0:
            commands.append(f"X: 0 Y: {vertical_dy}")
        target_channel_x = to_pos["x"] - 1 if to_pos["x"] % 2 == 1 else to_pos["x"]
        horizontal_dx = target_channel_x - channel_x
        if horizontal_dx != 0:
            commands.append(f"X: {horizontal_dx} Y: 0")
        return commands
    
    def _is_castling_move(self, from_square: str, to_square: str) -> bool:
        return (from_square, to_square) in {('e1', 'g1'), ('e1', 'c1'), ('e8', 'g8'), ('e8', 'c8')}
    
    def _plan_castling_path(self, king_from: str, king_to: str, is_white_move: bool) -> list:
        if king_to in ['g1', 'g8']:
            rook_from = 'h1' if is_white_move else 'h8'
            rook_to = 'f1' if is_white_move else 'f8'
        else:
            rook_from = 'a1' if is_white_move else 'a8'
            rook_to = 'd1' if is_white_move else 'd8'
        
        king_from_coords = self.converter.chess_to_grid(king_from, use_channel=False)
        king_to_coords = self.converter.chess_to_grid(king_to, use_channel=False)
        rook_from_coords = self.converter.chess_to_grid(rook_from, use_channel=False)
        rook_to_coords = self.converter.chess_to_grid(rook_to, use_channel=False)
        
        path = ["lower", "home"]
        path.extend(self._plan_edge_movement(self.home_position, king_from_coords, False))
        path.append("raise")
        path.extend(self._plan_edge_movement(king_from_coords, king_to_coords, True))
        path.append(f"X: 1 Y: 1")  # MOVE TO FINAL POSITION FIRST
        path.append("lower")       # THEN LOWER
        path.append("home")
        path.extend(self._plan_edge_movement(self.home_position, rook_from_coords, False))
        path.append("raise")
        path.extend(self._plan_edge_movement(rook_from_coords, rook_to_coords, True))
        path.append(f"X: 1 Y: 1")  # MOVE TO FINAL POSITION FIRST  
        path.append("lower")       # THEN LOWER
        return path