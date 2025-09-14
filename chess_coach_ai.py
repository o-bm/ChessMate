"""
Chess Coach AI - Voice-Friendly Chess Assistant
Optimized for text-to-speech output
"""

from groq import Groq
import json
import os
import re
import requests
import time
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
# Try both paths - from backend directory and from root
if os.path.exists('../config.env'):
    load_dotenv('../config.env')
else:
    load_dotenv('config.env')

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    # Try to help debug
    current_dir = os.getcwd()
    config_exists = os.path.exists('../config.env') or os.path.exists('config.env')
    raise ValueError(f"GROQ_API_KEY not found. Current dir: {current_dir}, config.env exists: {config_exists}")
    
groq_client = Groq(api_key=GROQ_API_KEY)

# API base URL
API_BASE = "http://localhost:9247"

print("Chess Coach AI initialized")

def remove_emojis(text):
    """Remove all emoji characters from text"""
    emoji_pattern = re.compile("["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map symbols
        u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        u"\U0001F900-\U0001F9FF"  # additional emoticons
        "]+", flags=re.UNICODE)
    return emoji_pattern.sub('', text)

# Tool definitions for Groq (removed get_legal_moves)
CHESS_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "make_move",
            "description": "Make a chess move when the user wants to move a piece",
            "parameters": {
                "type": "object",
                "properties": {
                    "from_square": {
                        "type": "string",
                        "description": "Starting square (e.g., 'e2')"
                    },
                    "to_square": {
                        "type": "string",
                        "description": "Target square (e.g., 'e4')"
                    }
                },
                "required": ["from_square", "to_square"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_position",
            "description": "Analyze the current position when user asks who's winning or wants analysis",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_hint",
            "description": "Get a hint when user asks for suggestions or best moves",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "explain_concept",
            "description": "Explain chess rules, concepts, or strategies when user asks about them",
            "parameters": {
                "type": "object",
                "properties": {
                    "concept": {
                        "type": "string",
                        "description": "The chess concept to explain"
                    }
                },
                "required": ["concept"]
            }
        }
    }
]

def get_game_state() -> Dict:
    """Get current game state from API"""
    try:
        response = requests.get(f"{API_BASE}/game")
        game_state = response.json()
        
        # Debug: print key game state info
        print(f"[DEBUG] Game State - Turn: {game_state.get('turn', 'unknown')}, "
              f"Moves: {len(game_state.get('move_history', []))}, "
              f"Last move: {game_state.get('move_history', ['none'])[-1] if game_state.get('move_history') else 'none'}")
        
        return game_state
    except Exception as e:
        print(f"[ERROR] Failed to get game state: {e}")
        return {"error": str(e)}

def process_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Process tool calls by interacting with the API"""
    
    print(f"[DEBUG] Tool called: {tool_name} with args: {arguments}")
    
    if tool_name == "make_move":
        from_sq = arguments.get("from_square")
        to_sq = arguments.get("to_square")
        
        # Call API to make the move
        try:
            response = requests.post(
                f"{API_BASE}/move",
                json={"from_sq": from_sq, "to_sq": to_sq},
                params={"source": "coach"}
            )
            
            if response.status_code == 200:
                data = response.json()
                # Make the response more coach-like
                move_msg = data["message"]
                # Add encouraging feedback
                coach_msg = f"Good move! {move_msg}"
                if "captures" in move_msg.lower():
                    coach_msg = f"Nice capture! {move_msg}"
                elif "check" in move_msg.lower():
                    coach_msg = f"Great job putting them in check! {move_msg}"
                elif "castle" in move_msg.lower():
                    coach_msg = f"Smart castling! {move_msg}"
                    
                return {
                    "success": True,
                    "message": remove_emojis(coach_msg),
                    "data": data
                }
            else:
                error_detail = response.json().get("detail", "Move failed")
                # Make error message voice-friendly
                if "Not your turn" in error_detail:
                    return {
                        "success": False,
                        "message": "Hold on, it's not your turn yet. Let your opponent make their move first.",
                        "data": {}
                    }
                elif "illegal" in error_detail.lower() or "invalid" in error_detail.lower():
                    return {
                        "success": False,
                        "message": "That move isn't legal in this position. Check if that piece can actually move there.",
                        "data": {}
                    }
                else:
                    return {
                        "success": False,
                        "message": "I couldn't make that move. Let's try a different piece or square.",
                        "data": {}
                    }
        except Exception as e:
            return {
                "success": False,
                "message": "I'm having trouble making that move. Let me reconnect to the board.",
                "data": {}
            }
    
    elif tool_name == "analyze_position":
        # Get game state and Stockfish analysis
        try:
            game_state = requests.get(f"{API_BASE}/game").json()
            analysis = requests.get(f"{API_BASE}/analyze").json()
            
            # Debug: print what we got from the API
            print(f"[DEBUG] Analysis data - Turn: {analysis.get('turn')}, "
                  f"Eval: {analysis.get('evaluation')}, "
                  f"Best moves: {[m['san'] for m in analysis.get('best_moves', [])[:2]]}, "
                  f"Phase: {analysis.get('phase')}")
            
            # Build voice-friendly prompt
            turn = analysis['turn']
            evaluation = analysis['evaluation']
            best_moves = [m['san'] for m in analysis['best_moves'][:2]]
            phase = analysis['phase']
            move_count = len(game_state.get("move_history", []))
            current_fen = game_state.get("fen", "")
            player_color = None
            
            # Determine who's better in simple terms
            if "Mate" in evaluation:
                eval_text = evaluation
            else:
                eval_value = float(evaluation)
                if abs(eval_value) < 0.5:
                    eval_text = "The position is roughly equal"
                elif eval_value > 0:
                    eval_text = f"White has an advantage of {abs(eval_value):.1f} pawns"
                else:
                    eval_text = f"Black has an advantage of {abs(eval_value):.1f} pawns"
            
            # Clean, focused prompt
            prompt = f"""
            Current position (FEN): {current_fen}
            Move {move_count // 2 + 1}, {turn} to move
            
            Computer evaluation: {eval_text}
            Recommended continuation: {best_moves[0]} {best_moves[1] if len(best_moves) > 1 else ''}
            Game phase: {phase}
            
            Provide a clear positional assessment covering:
            1. The key imbalance or advantage in this position
            2. The immediate plan for {turn}
            3. Why the suggested move {best_moves[0]} makes sense here
            
            Focus on concrete pieces and squares, not abstract concepts.
            """
            
            print(f"[DEBUG] Prompt to LLM for analysis:\n{prompt}")
            
            completion = groq_client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": f"You are an expert chess coach providing position analysis. The player is {player_color}, it's {turn}'s turn. Give insightful analysis in 2-3 sentences max. Focus on the most important strategic or tactical element. Speak naturally using square names like 'the knight on e5' rather than notation."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4  # Balanced for accuracy with some variety
            )
            
            return {
                "success": True,
                "message": remove_emojis(completion.choices[0].message.content),
                "data": analysis
            }
            
        except Exception as e:
            print(f"[ERROR] in analyze_position: {e}")
            return {
                "success": False,
                "message": "Let me take another look at the position. Can you try asking again?",
                "data": {}
            }
    
    elif tool_name == "get_hint":
        # Get game state and hint data from API
        try:
            game_state = requests.get(f"{API_BASE}/game").json()
            hint_data = requests.get(f"{API_BASE}/hint").json()
            
            print(f"[DEBUG] Hint data - Best moves: {hint_data.get('best_moves', [])[:2]}, "
                  f"Turn: {hint_data.get('turn')}")
            
            if not hint_data.get('best_moves'):
                return {
                    "success": True,
                    "message": "This position is complex. Consider improving your piece coordination or controlling the center.",
                    "data": {}
                }
            
            # Get comprehensive context
            best_move = hint_data['best_moves'][0]
            second_best = hint_data['best_moves'][1] if len(hint_data.get('best_moves', [])) > 1 else None
            turn = hint_data['turn']
            move_count = len(game_state.get("move_history", []))
            player_color = game_state.get("online_player_color", "black")
            
            # Get ALL context needed
            full_move_history = game_state.get("move_history", [])
            current_fen = game_state.get("fen", "")
            piece_positions = hint_data.get("piece_positions", {})
            
            # Parse the move details
            move_notation = best_move['san']
            move_uci = best_move.get('move', '')
            
            # Extract from and to squares
            from_square = move_uci[:2] if len(move_uci) >= 4 else ""
            to_square = move_uci[2:4] if len(move_uci) >= 4 else ""
            
            # Get piece information
            moving_piece_info = piece_positions.get(from_square, {})
            moving_piece = moving_piece_info.get("piece", "piece")
            
            target_piece_info = piece_positions.get(to_square, {})
            target_piece = target_piece_info.get("piece") if target_piece_info else None
            
            # Determine move characteristics
            is_capture = 'x' in move_notation or target_piece is not None
            is_check = '+' in move_notation
            is_checkmate = '#' in move_notation
            is_castle = 'O-O' in move_notation
            
            # Determine if this is player's turn
            is_player_turn = (turn == player_color)
            
            # Craft focused, helpful prompts
            if is_player_turn:
                # When it's the player's turn - give actionable advice
                capture_text = f"capturing the {target_piece}" if is_capture and target_piece else ""
                check_text = "This delivers check!" if is_check else "This delivers checkmate!" if is_checkmate else ""
                
                prompt = f"""
                Position (FEN): {current_fen}
                Your turn as {player_color}, move {move_count // 2 + 1}
                
                The strongest move here is {move_notation}: your {moving_piece} from {from_square} to {to_square} {capture_text}
                {check_text}
                {f"Alternative: {second_best['san']}" if second_best else ""}
                
                Explain why this {moving_piece} move to {to_square} is powerful in this specific position.
                What does it achieve tactically or strategically?
                Keep it practical - mention specific pieces and squares.
                """
            else:
                # When it's opponent's turn - prepare the player
                threat_text = f"capturing your {target_piece}" if is_capture and target_piece else "creating threats"
                check_text = "putting you in check" if is_check else ""
                
                prompt = f"""
                Position (FEN): {current_fen}
                Opponent's turn ({turn}), move {move_count // 2 + 1}
                You are {player_color}
                
                The opponent will likely play {move_notation}: their {moving_piece} from {from_square} to {to_square}, {threat_text} {check_text}
                
                Explain the threat this creates and suggest how to prepare your response.
                Be specific about which of your pieces can defend or counter-attack.
                """
            
            print(f"[DEBUG] Hint prompt for {'player' if is_player_turn else 'opponent'} turn")
            
            completion = groq_client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": f"You are a skilled chess coach providing move recommendations. {'Help the player find the best move' if is_player_turn else 'Help the player prepare for the opponents move'}. Be specific and practical - mention actual pieces and squares. 2-3 sentences maximum. Natural speech like 'your bishop on c1 can pressure the long diagonal' not chess notation."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3  # Lower for consistency
            )
            
            return {
                "success": True,
                "message": remove_emojis(completion.choices[0].message.content),
                "data": {
                    "best_move": best_move['san'],
                    "evaluation": best_move.get('evaluation'),
                    "is_player_turn": is_player_turn
                }
            }
            
        except Exception as e:
            print(f"[ERROR] in get_hint: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "message": "Let me think about this position a bit more. Ask me again in a moment.",
                "data": {}
            }
    
    elif tool_name == "explain_concept":
        concept = arguments.get("concept", "")
        
        # Voice-friendly prompt for explanations
        prompt = f"""
        Explain the chess concept: {concept}
        
        Give a clear, simple explanation in 2-3 sentences. Include an example if helpful.
        """
        
        print(f"[DEBUG] Concept explanation prompt: {concept}")
        
        try:
            completion = groq_client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": "You are a chess coach. Give clear analysis in 2-3 sentences. Be encouraging but concise. No emojis, no formatting."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.5
            )
            
            return {
                "success": True,
                "message": remove_emojis(completion.choices[0].message.content),
                "data": {"concept": concept}
            }
        except Exception as e:
            return {
                "success": False,
                "message": "Let me gather my thoughts on that topic. Can you ask me again?",
                "data": {}
            }
    
    return {
        "success": False,
        "message": "I'm not sure what you're asking. Could you rephrase that for me?",
        "data": {}
    }

def process_user_input(user_input: str):
    """Process user input through Groq and handle tool calls"""
    
    print(f"\nUser: {user_input}")
    
    # Small delay to prevent rate limiting
    time.sleep(0.5)
    
    # Get current game state for context
    game_state = get_game_state()
    
    if "error" in game_state:
        print(f"Failed to get game state: {game_state['error']}")
        return {
            "success": False,
            "message": "I'm having trouble seeing the board. Let's make sure the game is running properly.",
            "data": {}
        }
    
    move_count = len(game_state.get("move_history", []))
    recent_moves = game_state.get("move_history", [])[-3:]  # Less history for voice
    turn = game_state.get("turn", "white")
    
    # Get more detailed game info - FIX THE HARDCODED PLAYER COLOR
    fen = game_state.get("fen", "")
    player_color = game_state.get("online_player_color", "black")  # Get from game state!
    
    # Voice-optimized system prompt with better context
    system_prompt = f"""You are an experienced chess coach guiding a student who is playing as {player_color}.

Current position: Move {move_count // 2 + 1}, {turn} to move
Recent game: {', '.join(recent_moves[-5:]) if recent_moves else 'Opening phase'}

Key context:
- It's currently {turn}'s turn ({"your move" if turn == player_color else "opponent's move"})
- Provide practical, actionable advice
- Use natural language with square names, not chess notation
- Keep responses concise but insightful (2-3 sentences)

Available tools:
- make_move: Execute a move (only on player's turn)
- analyze_position: Evaluate who's winning and why
- get_hint: Get the best move with explanation
- explain_concept: Clarify chess rules or strategies

Remember: The player is {player_color}, so {"help them choose their move" if turn == player_color else "explain what the opponent might do"}."""
    
    print(f"[DEBUG] System prompt preview (first 200 chars): {system_prompt[:200]}...")
    print(f"[DEBUG] Key context - Turn: {turn}, Player: {player_color}, Move: {move_count // 2 + 1}")
    
    try:
        # Call Groq with tools
        print(f"Calling Groq API...")
        completion = groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ],
            tools=CHESS_TOOLS,
            tool_choice="auto",
            temperature=0.5,  # Balanced temperature for natural but focused responses
            timeout=30  # Add explicit timeout
        )
        
        response = completion.choices[0].message
        print(f"Groq API responded")
        
        # Check for tool calls
        if response.tool_calls:
            tool_call = response.tool_calls[0]
            tool_name = tool_call.function.name
            
            # Parse arguments safely
            try:
                tool_args = json.loads(tool_call.function.arguments)
                # Clean up empty string keys that Groq sometimes generates
                if '' in tool_args:
                    del tool_args['']
            except json.JSONDecodeError:
                # If JSON parsing fails, use empty dict
                tool_args = {}
            
            print(f"[DEBUG] LLM chose tool: {tool_name}")
            print(f"[DEBUG] Tool args: {tool_args}")
            
            # Process the tool
            result = process_tool(tool_name, tool_args)
            
            # Remove any emojis from tool responses too
            result['message'] = remove_emojis(result.get('message', ''))
            
            print(f"Coach: {result['message']}")
            
            return result
        else:
            # Regular response - make sure it's voice-friendly
            print(f"[DEBUG] LLM gave direct response (no tool)")
            message = response.content
            # Remove any markdown or formatting that might have slipped through
            message = message.replace('*', '').replace('_', '').replace('#', '')
            
            # Remove common emojis if any slip through
            message = remove_emojis(message)
            
            print(f"Coach: {message}")
            return {
                "success": True,
                "message": message,
                "data": {}
            }
            
    except Exception as e:
        print(f"Error in process_user_input: {e}")
        import traceback
        traceback.print_exc()
        
        # More specific error messages
        if "timeout" in str(e).lower():
            return {
                "success": False,
                "message": "That's taking a bit longer than expected. Let's try again.",
                "data": {}
            }
        elif "rate" in str(e).lower():
            return {
                "success": False,
                "message": "I need a quick break. Give me a moment and ask again.",
                "data": {}
            }
        else:
            return {
                "success": False,
                "message": "Hmm, something went wrong. Could you try asking that again?",
                "data": {}
            }

if __name__ == "__main__":
    print("Chess Coach AI - Voice-Optimized Mode")
    print("="*50)
    print("Make sure the backend is running: cd backend && uvicorn main:app --reload")
    print("="*50)
    
    # Interactive mode
    print("\nTalk to your chess coach (type 'quit' to exit):\n")
    
    while True:
        user_input = input("You: ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\nGoodbye! Keep practicing!")
            break
        
        if user_input:
            result = process_user_input(user_input)
            # For voice mode, we could add TTS here:
            # speak(result['message'])
            print("-"*50)