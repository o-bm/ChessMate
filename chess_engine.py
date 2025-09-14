"""
Chess Engine Integration with Stockfish
Provides raw chess data and analysis - no hardcoded responses
"""

import chess
import chess.pgn
from stockfish import Stockfish
from typing import Dict, List, Optional
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('config.env')

class ChessEngine:
    def __init__(self, stockfish_path: str = "/opt/homebrew/bin/stockfish"):
        """Initialize chess engine with Stockfish"""
        
        # Initialize the chess board
        self.board = chess.Board()
        
        # Initialize Stockfish
        try:
            self.engine = Stockfish(
                path=stockfish_path,
                depth=15,
                parameters={
                    "Threads": 2,
                    "Hash": 256,
                    "Min Split Depth": 0,
                    "Minimum Thinking Time": 20,
                    "Slow Mover": 80
                }
            )
            print(f"Stockfish initialized successfully at {stockfish_path}")
        except Exception as e:
            print(f"Failed to initialize Stockfish: {e}")
            print("Make sure Stockfish is installed: brew install stockfish")
            self.engine = None
    
    def reset_board(self):
        """Reset the chess board to starting position"""
        self.board.reset()
        if self.engine:
            self.engine.set_fen_position(self.board.fen())
        return self.board.fen()
    
    def make_move(self, from_square: str, to_square: str, promotion: str = None) -> Dict:
        """
        Make a move on the board
        Returns: Dict with success status, new FEN, and move info
        """
        try:
            # Create move object
            move = chess.Move.from_uci(f"{from_square}{to_square}{promotion or ''}")
            
            # Check if move is legal
            if move not in self.board.legal_moves:
                legal_moves = [m.uci() for m in self.board.legal_moves 
                              if str(m)[:2] == from_square]
                return {
                    "success": False,
                    "error": "Illegal move",
                    "legal_alternatives": legal_moves,
                    "fen": self.board.fen()
                }
            
            # Make the move
            san_notation = self.board.san(move)
            self.board.push(move)
            
            # Update engine position
            if self.engine:
                self.engine.set_fen_position(self.board.fen())
            
            # Check game status
            game_status = self._check_game_status()
            
            return {
                "success": True,
                "move": move.uci(),
                "san": san_notation,
                "fen": self.board.fen(),
                "turn": "white" if self.board.turn else "black",
                **game_status
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "fen": self.board.fen()
            }
    
    def analyze_position(self, depth: int = 15) -> Dict:
        """
        Analyze current position with Stockfish
        Returns raw evaluation and best moves
        """
        if not self.engine:
            return {
                "error": "Stockfish not initialized",
                "evaluation": "0.0",
                "best_moves": []
            }
        
        # Set position ONCE
        self.engine.set_fen_position(self.board.fen())
        self.engine.set_depth(depth)
        
        # Get evaluation
        evaluation = self.engine.get_evaluation()
        
        # Get top 3 moves in ONE call - FIX THE DUPLICATE ISSUE
        best_moves = []
        try:
            # Get all top moves at once
            top_moves = self.engine.get_top_moves(3)
            for move_data in top_moves:
                try:
                    move_uci = move_data["Move"]
                    move = chess.Move.from_uci(move_uci)
                    best_moves.append({
                        "move": move_uci,
                        "san": self.board.san(move),
                        "evaluation": self._format_evaluation(move_data.get("Centipawn", 0))
                    })
                except Exception as e:
                    print(f"[DEBUG] Error processing move {move_data}: {e}")
                    continue
        except Exception as e:
            print(f"[ERROR] Getting top moves: {e}")
        
        # Determine game phase
        phase = self._get_game_phase()
        
        # Format evaluation for display
        eval_display = self._format_evaluation_display(evaluation)
        
        return {
            "evaluation": eval_display,
            "raw_evaluation": evaluation,
            "best_moves": best_moves,
            "phase": phase,
            "fen": self.board.fen(),
            "move_count": len(self.board.move_stack),
            "turn": "white" if self.board.turn else "black",
            "piece_count": len(self.board.piece_map())
        }
    
    def get_legal_moves(self, square: str = None) -> Dict:
        """Get all legal moves, optionally for a specific square"""
        
        legal_moves = []
        
        if square:
            try:
                square_obj = chess.parse_square(square.lower())
                piece = self.board.piece_at(square_obj)
                
                if not piece:
                    return {
                        "square": square,
                        "piece": None,
                        "moves": [],
                        "message": f"No piece on {square}"
                    }
                
                # Get moves for this piece
                for move in self.board.legal_moves:
                    if move.from_square == square_obj:
                        legal_moves.append({
                            "to": chess.square_name(move.to_square),
                            "san": self.board.san(move),
                            "captures": self.board.is_capture(move)
                        })
                
                return {
                    "square": square,
                    "piece": piece.symbol(),
                    "piece_name": chess.piece_name(piece.piece_type),
                    "moves": legal_moves,
                    "count": len(legal_moves)
                }
                
            except Exception as e:
                return {
                    "error": str(e),
                    "square": square,
                    "moves": []
                }
        else:
            # Get all legal moves
            for move in self.board.legal_moves:
                legal_moves.append({
                    "from": chess.square_name(move.from_square),
                    "to": chess.square_name(move.to_square),
                    "san": self.board.san(move)
                })
            
            return {
                "total_moves": len(legal_moves),
                "moves": legal_moves,
                "turn": "white" if self.board.turn else "black"
            }
    
    def _check_game_status(self) -> Dict:
        """Check current game status"""
        return {
            "is_check": self.board.is_check(),
            "is_checkmate": self.board.is_checkmate(),
            "is_stalemate": self.board.is_stalemate(),
            "is_draw": self.board.is_insufficient_material() or self.board.is_seventyfive_moves(),
            "can_claim_draw": self.board.can_claim_threefold_repetition() or self.board.can_claim_fifty_moves()
        }
    
    def _get_game_phase(self) -> str:
        """Determine current game phase"""
        move_count = len(self.board.move_stack)
        piece_count = len(self.board.piece_map())
        
        if move_count < 10:
            return "opening"
        elif piece_count > 16:
            return "middlegame"
        else:
            return "endgame"
    
    def _format_evaluation(self, centipawns: int) -> str:
        """Format centipawn evaluation to human-readable"""
        pawns = centipawns / 100
        if pawns > 0:
            return f"+{pawns:.2f}"
        else:
            return f"{pawns:.2f}"
    
    def _format_evaluation_display(self, evaluation: Dict) -> str:
        """Format Stockfish evaluation for display"""
        if evaluation["type"] == "mate":
            if evaluation["value"] > 0:
                return f"Mate in {evaluation['value']}"
            else:
                return f"Mate in {-evaluation['value']} for opponent"
        else:
            pawns = evaluation["value"] / 100
            # FIX: Remove the incorrect flipping of evaluation for Black's turn
            # Stockfish always gives evaluation from White's perspective
            # Positive = White is better, Negative = Black is better
            
            if pawns > 0:
                return f"+{pawns:.2f}"
            else:
                return f"{pawns:.2f}"
    
    def get_fen(self) -> str:
        """Get current FEN position"""
        return self.board.fen()
    
    def set_fen(self, fen: str) -> bool:
        """Set position from FEN"""
        try:
            self.board.set_fen(fen)
            if self.engine:
                self.engine.set_fen_position(fen)
            return True
        except:
            return False
    
    def get_move_history(self) -> List[str]:
        """Get move history in SAN notation"""
        temp_board = chess.Board()
        moves = []
        for move in self.board.move_stack:
            moves.append(temp_board.san(move))
            temp_board.push(move)
        return moves
    
    def get_board_info(self) -> Dict:
        """Get comprehensive board information"""
        return {
            "fen": self.board.fen(),
            "turn": "white" if self.board.turn else "black",
            "move_history": self.get_move_history(),
            "move_count": len(self.board.move_stack),
            "is_check": self.board.is_check(),
            "is_checkmate": self.board.is_checkmate(),
            "is_stalemate": self.board.is_stalemate(),
            "piece_count": len(self.board.piece_map()),
            "legal_moves_count": self.board.legal_moves.count()
        }


# Test the engine
if __name__ == "__main__":
    print("Chess Engine Test")
    print("="*50)
    
    engine = ChessEngine()
    
    # Test 1: Make a move
    print("\n1. Testing move e2-e4:")
    result = engine.make_move("e2", "e4")
    print(f"   Success: {result['success']}")
    print(f"   SAN: {result.get('san')}")
    
    # Test 2: Analyze position
    print("\n2. Analyzing position:")
    analysis = engine.analyze_position()
    print(f"   Evaluation: {analysis['evaluation']}")
    print(f"   Best moves: {[m['san'] for m in analysis['best_moves']]}")
    print(f"   Turn: {analysis['turn']}")
    
    # Test 3: Get legal moves
    print("\n3. Legal moves from g1:")
    moves = engine.get_legal_moves("g1")
    print(f"   Piece: {moves.get('piece_name')}")
    print(f"   Move count: {moves.get('count', 0)}")
    
    # Test 4: Board info
    print("\n4. Board information:")
    info = engine.get_board_info()
    print(f"   Turn: {info['turn']}")
    print(f"   Legal moves available: {info['legal_moves_count']}")
    
    print("\nEngine test complete!")