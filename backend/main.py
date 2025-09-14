# main.py
from fastapi import FastAPI, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import chess
import sys
import os
import tempfile
from typing import Optional
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from chess_engine import ChessEngine

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the chess board and engine
BOARD = chess.Board()
ENGINE = ChessEngine()
MOVE_HISTORY: list[str] = []
MOVE_DETAILS = []

# Game configuration
GAME_CONFIG = {
    "online_player_color": "black",
    "physical_player_color": "white",
    "game_mode": "physical",
}

class MoveRequest(BaseModel):
    from_sq: str
    to_sq: str
    promotion: str | None = None

class SquareRequest(BaseModel):
    square: str

class GameState(BaseModel):
    fen: str
    turn: str
    is_check: bool
    is_checkmate: bool
    is_stalemate: bool
    move_history: list[str]
    last_move: dict | None
    online_player_color: str
    game_started: bool

class GameConfig(BaseModel):
    online_player_color: str

class AnalysisResponse(BaseModel):
    evaluation: str
    best_moves: list[dict]
    phase: str
    turn: str

class HintResponse(BaseModel):
    best_moves: list[dict]
    turn: str
    piece_positions: dict

def _state(last_move: chess.Move | None = None) -> GameState:
    lm = None
    if last_move:
        lm = {
            "from": chess.square_name(last_move.from_square),
            "to": chess.square_name(last_move.to_square),
        }
    return GameState(
        fen=BOARD.fen(),
        turn="white" if BOARD.turn == chess.WHITE else "black",
        is_check=BOARD.is_check(),
        is_checkmate=BOARD.is_checkmate(),
        is_stalemate=BOARD.is_stalemate(),
        move_history=MOVE_HISTORY,
        last_move=lm,
        online_player_color=GAME_CONFIG["online_player_color"],
        game_started=len(MOVE_HISTORY) > 0,
    )

@app.get("/game", response_model=GameState)
def get_game():
    """Get current game state"""
    return _state()

@app.post("/move", response_model=dict)
def make_move(req: MoveRequest, source: str = "web"):
    """Make a move on the board"""
    current_turn = "white" if BOARD.turn == chess.WHITE else "black"
    
    # No validation - allow all moves from any source
    
    uci = req.from_sq + req.to_sq + (req.promotion or "")
    try:
        move = chess.Move.from_uci(uci)
    except ValueError:
        raise HTTPException(400, detail="Malformed move.")

    if move not in BOARD.legal_moves:
        if req.promotion is None:
            try_q = chess.Move.from_uci(req.from_sq + req.to_sq + "q")
            if try_q in BOARD.legal_moves:
                move = try_q
            else:
                raise HTTPException(400, detail="Illegal move.")
        else:
            raise HTTPException(400, detail="Illegal move.")
    
    # Get piece that's moving
    piece = BOARD.piece_at(move.from_square)
    piece_name = chess.piece_name(piece.piece_type) if piece else "piece"
    # for the move details
    is_capture = BOARD.is_capture(move)
    is_castle = BOARD.is_castling(move)
    is_promotion = move.promotion is not None
    ############
    san_move = BOARD.san(move) 
    BOARD.push(move)
    MOVE_HISTORY.append(san_move)
    
    # Sync engine with board state
    ENGINE.set_fen(BOARD.fen())

    
    # Build response message
    message = f"Moved {piece_name} from {req.from_sq} to {req.to_sq} ({san_move})"
    if BOARD.is_check():
        message += " - Check!"
    if BOARD.is_checkmate():
        message += " - Checkmate! Game over."
    elif BOARD.is_stalemate():
        message += " - Stalemate! Game is a draw."

    MOVE_DETAILS.append({
        'from': req.from_sq,
        'to': req.to_sq,
        'is_white': current_turn == "white",  # true for white, false for black
        'is_capture': is_capture,
        'is_promotion': is_promotion,
        'is_castle': is_castle,
        'source': source
    })

    return {
        "success": True,
        "message": message,
        "san": san_move,
        "state": _state(last_move=move).model_dump()
    }

@app.get("/analyze", response_model=AnalysisResponse)
def analyze_position():
    """Get Stockfish analysis of current position"""
    # Sync engine with current board
    ENGINE.set_fen(BOARD.fen())
    
    # Get analysis from Stockfish
    analysis = ENGINE.analyze_position(depth=15)
    
    return AnalysisResponse(
        evaluation=analysis["evaluation"],
        best_moves=analysis["best_moves"],
        phase=analysis["phase"],
        turn=analysis["turn"]
    )

@app.get("/hint", response_model=HintResponse)
def get_hint():
    """Get top moves and piece positions for hints"""
    # Sync engine with current board
    ENGINE.set_fen(BOARD.fen())
    
    # Get analysis from Stockfish
    analysis = ENGINE.analyze_position(depth=20)
    
    # Get piece positions (what piece is on what square)
    piece_positions = {}
    for square in chess.SQUARES:
        piece = BOARD.piece_at(square)
        if piece:
            square_name = chess.square_name(square)
            piece_positions[square_name] = {
                "piece": chess.piece_name(piece.piece_type),
                "color": "white" if piece.color else "black",
                "symbol": piece.symbol()
            }
    
    return HintResponse(
        best_moves=analysis["best_moves"],
        turn=analysis["turn"],
        piece_positions=piece_positions
    )

@app.get("/robot/moves")
def get_robot_moves():
    """Get move details for robot"""
    return {"moves": MOVE_DETAILS}


@app.post("/legal-moves", response_model=dict)
def legal_moves(req: SquareRequest):
    """Get legal moves for a piece on a square"""
    try:
        from_sq = chess.parse_square(req.square)
    except ValueError:
        raise HTTPException(400, detail="Bad square.")

    legal = []
    for m in BOARD.legal_moves:
        if m.from_square == from_sq:
            legal.append({
                "from": chess.square_name(m.from_square),
                "to": chess.square_name(m.to_square),
            })
    return {"legal_moves": legal}

@app.post("/reset", response_model=GameState)
def reset():
    """Reset the game"""
    BOARD.reset()
    MOVE_HISTORY.clear()
    MOVE_DETAILS.clear()
    ENGINE.reset_board()
    return _state()

@app.post("/configure", response_model=GameConfig)
def configure_game(config: GameConfig):
    """Configure game settings"""
    if len(MOVE_HISTORY) > 0:
        raise HTTPException(400, detail="Cannot change color after game has started. Reset the game first.")
    
    GAME_CONFIG["online_player_color"] = config.online_player_color
    GAME_CONFIG["physical_player_color"] = "white" if config.online_player_color == "black" else "black"
    
    return GameConfig(
        online_player_color=GAME_CONFIG["online_player_color"]
    )

@app.get("/config", response_model=GameConfig)
def get_config():
    """Get current game configuration"""
    return GameConfig(
        online_player_color=GAME_CONFIG["online_player_color"]
    )

# Coach endpoints
class CoachRequest(BaseModel):
    text: str

@app.post("/coach/text")
def coach_text(request: CoachRequest):
    """Process text command for the chess coach"""
    try:
        # Import here to avoid circular dependencies
        from chess_coach_ai import process_user_input
        from dotenv import load_dotenv
        import base64
        import re
        import asyncio  # ADD THIS IMPORT
        import concurrent.futures  # ADD THIS IMPORT
        
        # Load environment variables
        load_dotenv('../config.env')
        load_dotenv('config.env')
        
        # FIX: Run in thread pool to avoid deadlock
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(process_user_input, request.text)
            result = future.result(timeout=30)
        
        # Generate TTS for text commands too
        audio_response_base64 = None
        if result.get("message"):
            try:
                from groq import Groq
                
                api_key = os.getenv("GROQ_TTS_API_KEY") or os.getenv("GROQ_API_KEY")  # Try TTS key first
                if api_key:
                    groq_client = Groq(api_key=api_key)
                    print(f"Using TTS API key")
                    
                    # Clean text for speech and fix chess notation pronunciation
                    clean_text = result["message"].replace('*', '').replace('_', '').replace('#', '').replace('`', '')
                    # Fix chess position pronunciation (e.g., "e4" -> "e 4", "Nf3" -> "N f 3")
                    clean_text = re.sub(r'([a-h])([1-8])', r'\1 \2', clean_text)
                    clean_text = re.sub(r'([KQRBN])([a-h])([1-8])', r'\1 \2 \3', clean_text)
                    # Don't truncate the response
                    
                    print(f"Generating TTS for text command: {clean_text[:50]}...")
                    
                    # Generate speech with Groq - Calum voice at faster speed
                    response = groq_client.audio.speech.create(
                        model="playai-tts",
                        voice="Calum-PlayAI",
                        input=clean_text,
                        response_format="wav",
                        speed=1.15  # Slightly faster speech
                    )
                    
                    # Save to temp file first (Groq SDK requires this)
                    # REMOVED: import tempfile - it's already imported at line 8!
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
                        response.write_to_file(temp_audio.name)
                        # Read the file back as bytes
                        with open(temp_audio.name, 'rb') as f:
                            audio_bytes = f.read()
                        # Clean up temp file
                        os.unlink(temp_audio.name)
                    
                    audio_response_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                    print(f"TTS generated successfully for text command")
                    
            except Exception as tts_error:
                # Check if it's a rate limit error
                if "rate_limit_exceeded" in str(tts_error) or "429" in str(tts_error):
                    print(f"TTS rate limit hit - falling back to browser TTS")
                    # Leave audio_response_base64 as None - frontend will use browser TTS
                else:
                    print(f"TTS error: {tts_error}")
                    import traceback
                    traceback.print_exc()
                # Fall back to no audio (browser will use its TTS)
                pass
        
        return {
            "success": result.get("success", True),
            "message": result.get("message", ""),
            "audio_response": audio_response_base64,
            "data": result.get("data", {})
        }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "audio_response": None,
            "data": {}
        }

@app.post("/coach/audio")
async def coach_audio(audio: UploadFile = File(...)):
    """Process audio command for the chess coach using Groq Whisper"""
    try:
        # Import here to avoid circular dependencies
        from voice_coach import VoiceCoach
        import base64
        from dotenv import load_dotenv
        import asyncio  # ADD THIS IMPORT
        
        # Load environment variables
        load_dotenv('../config.env')
        load_dotenv('config.env')
        
        print(f"Received audio file: {audio.filename}, content_type: {audio.content_type}")
        
        # Determine file extension from content type or filename
        if audio.content_type and 'wav' in audio.content_type:
            suffix = '.wav'
        elif audio.filename and audio.filename.endswith('.wav'):
            suffix = '.wav'
        elif audio.content_type and 'mp4' in audio.content_type:
            suffix = '.mp4'
        elif audio.filename and audio.filename.endswith('.mp4'):
            suffix = '.mp4'
        else:
            suffix = '.webm'
        
        # Save uploaded audio to temp file for Groq Whisper
        # tempfile is already imported at top of file (line 8)
        temp_audio = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        content = await audio.read()
        temp_audio.write(content)
        temp_audio.close()
        
        print(f"Saved audio to temp file: {temp_audio.name}, size: {len(content)} bytes")
        
        # Process with voice coach (this uses Groq Whisper internally)
        coach = VoiceCoach()
        
        # Transcribe using Groq Whisper
        transcription = coach.transcribe_audio(temp_audio.name)
        print(f"Groq Whisper transcription: {transcription}")
        if not transcription:
            return {
                "success": False,
                "message": "Could not understand the audio. Please try again.",
                "transcription": "",
                "audio_response": None,
                "data": {}
            }
        
        # Enhance command if needed
        command = coach.enhance_command(transcription)
        print(f"Enhanced command: {command}")
        
        # Process command - FIX: RUN IN SEPARATE THREAD TO AVOID DEADLOCK
        from chess_coach_ai import process_user_input
        
        # THIS IS THE KEY FIX - run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, process_user_input, command)
        
        print(f"Process result: success={result.get('success')}, message length={len(result.get('message', ''))}")
        
        # Generate voice response using Groq TTS with Calum voice
        audio_response_base64 = None
        if result.get("message"):
            try:
                from groq import Groq
                import re
                
                api_key = os.getenv("GROQ_TTS_API_KEY") or os.getenv("GROQ_API_KEY")
                if api_key:
                    groq_client = Groq(api_key=api_key)
                    print(f"Using TTS API key: {api_key[:10]}...")
                    
                    # Clean text for speech
                    clean_text = result["message"].replace('*', '').replace('_', '').replace('#', '').replace('`', '')
                    # Fix chess notation pronunciation
                    clean_text = re.sub(r'([a-h])([1-8])', r'\1 \2', clean_text)
                    clean_text = re.sub(r'([KQRBN])([a-h])([1-8])', r'\1 \2 \3', clean_text)
                    
                    print(f"Generating TTS for: {clean_text[:50]}...")
                    
                    # Generate speech with Groq TTS
                    response = groq_client.audio.speech.create(
                        model="playai-tts",
                        voice="Calum-PlayAI",
                        input=clean_text,
                        response_format="wav",
                        speed=1.15
                    )
                    
                    # Save TTS response to temp file
                    # DON'T import tempfile again - it's already available!
                    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_tts:
                        response.write_to_file(temp_tts.name)
                        # Read the file back as bytes
                        with open(temp_tts.name, 'rb') as f:
                            audio_bytes = f.read()
                        # Clean up temp file
                        os.unlink(temp_tts.name)
                    
                    audio_response_base64 = base64.b64encode(audio_bytes).decode('utf-8')
                    print(f"TTS generated successfully, size: {len(audio_response_base64)} chars")
                
            except Exception as tts_error:
                # Check if it's a rate limit error
                if "rate_limit_exceeded" in str(tts_error) or "429" in str(tts_error):
                    print(f"TTS rate limit hit - falling back to browser TTS")
                    # Leave audio_response_base64 as None - frontend will use browser TTS
                else:
                    print(f"TTS error: {tts_error}")
                    import traceback
                    traceback.print_exc()
                # Fall back to no audio (browser will use its TTS)
                pass
        
        return {
            "success": result.get("success", False),
            "message": result.get("message", ""),
            "transcription": transcription,
            "audio_response": audio_response_base64,
            "data": result.get("data", {})
        }
        
    except Exception as e:
        print(f"Coach audio error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "message": f"Error processing audio: {str(e)}",
            "transcription": "",
            "audio_response": None,
            "data": {}
        }
    finally:
        # Clean up temp file
        try:
            if 'temp_audio' in locals() and hasattr(temp_audio, 'name'):
                os.unlink(temp_audio.name)
        except:
            pass