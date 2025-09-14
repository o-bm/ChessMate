'use client';

import { useState, useEffect, useRef } from 'react';
import chessApiService from './services/chessApi';
import { ChessPieces } from './components/ChessPieces';

export default function ChessGame() {
  // Simple state - no physical/online distinction
  const [board, setBoard] = useState([]);
  const [turn, setTurn] = useState('white');
  const [moveHistory, setMoveHistory] = useState([]);
  const [selectedSquare, setSelectedSquare] = useState(null);
  const [legalMoves, setLegalMoves] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastMove, setLastMove] = useState(null);
  const [isCheck, setIsCheck] = useState(false);
  const [isCheckmate, setIsCheckmate] = useState(false);
  const [isStalemate, setIsStalemate] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const [playingAs, setPlayingAs] = useState('white');
  const [isRecording, setIsRecording] = useState(false);
  const [coachTextInput, setCoachTextInput] = useState('');
  const [chatHistory, setChatHistory] = useState([]);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const currentAudioRef = useRef(null);
  const chatEndRef = useRef(null);
  const moveHistoryRef = useRef(null);

  // Convert FEN to 8x8 board array
  const fenToBoard = (fen) => {
    if (!fen) return [];
    const position = fen.split(' ')[0];
    const rows = position.split('/');
    const boardArray = [];
    
    for (let row of rows) {
      const boardRow = [];
      for (let char of row) {
        if (isNaN(char)) {
          boardRow.push(char);
        } else {
          for (let i = 0; i < parseInt(char); i++) {
            boardRow.push(null);
          }
        }
      }
      boardArray.push(boardRow);
    }
    
    return boardArray;
  };

  // Load game state from backend
  const loadGame = async () => {
    try {
      setLoading(true);
      const state = await chessApiService.getGameState();
      
      // Update all state from backend
      setBoard(fenToBoard(state.fen));
      setTurn(state.turn);
      setMoveHistory(state.move_history || []);
      setIsCheck(state.is_check);
      setIsCheckmate(state.is_checkmate);
      setIsStalemate(state.is_stalemate);
      
      if (state.last_move) {
        setLastMove(state.last_move);
      }
      
      setError(null);
    } catch (err) {
      console.error('Failed to load game:', err);
      setError('Failed to connect to game server');
      // Set default board on error
      setBoard(fenToBoard('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'));
    } finally {
      setLoading(false);
    }
  };

  // Initial load and setup with smart polling
  useEffect(() => {
    loadGame();
    
    // Check if mobile
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    checkMobile();
    window.addEventListener('resize', checkMobile);
    
    // Smart polling - only update if game state actually changed
    const pollInterval = setInterval(async () => {
      try {
        const state = await chessApiService.getGameState();
        // Only update if move history changed (new move was made)
        setMoveHistory(prevHistory => {
          if (state.move_history && state.move_history.length !== prevHistory.length) {
            // Update all state only if there's a change
            setBoard(fenToBoard(state.fen));
            setTurn(state.turn);
            setIsCheck(state.is_check);
            setIsCheckmate(state.is_checkmate);
            setIsStalemate(state.is_stalemate);
            if (state.last_move) {
              setLastMove(state.last_move);
            }
            return state.move_history || [];
          }
          return prevHistory;
        });
      } catch (err) {
        // Silently ignore polling errors
      }
    }, 2000); // Poll every 2 seconds
    
    // Cleanup
    return () => {
      clearInterval(pollInterval);
      window.removeEventListener('resize', checkMobile);
      stopCurrentAudio(); // Stop any playing audio on unmount
    };
  }, []); // Empty dependency array - only run once on mount

  // Auto-scroll move history when it updates
  useEffect(() => {
    if (moveHistoryRef.current) {
      moveHistoryRef.current.scrollTop = moveHistoryRef.current.scrollHeight;
    }
  }, [moveHistory]);
  
  // Auto-scroll chat when new messages arrive
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatHistory]);
  
  // Clear check alert when check is resolved (but not checkmate/stalemate)
  useEffect(() => {
    if (!isCheck && error === 'Check!') {
      setError(null);
    }
  }, [isCheck, error]);
  
  // Stop audio when voice is disabled
  useEffect(() => {
    if (!voiceEnabled) {
      stopCurrentAudio();
    }
  }, [voiceEnabled]);

  // Get legal moves for a piece
  const getLegalMoves = async (square) => {
    try {
      const response = await chessApiService.getLegalMoves(square);
      return response.legal_moves || [];
    } catch (err) {
      console.error('Failed to get legal moves:', err);
      return [];
    }
  };

  // Convert row/col to chess notation (accounting for board perspective)
  const squareToNotation = (row, col) => {
    // When playing as black, the board is flipped visually but we need to convert to actual board coordinates
    const actualRow = playingAs === 'black' ? (7 - row) : row;
    const actualCol = playingAs === 'black' ? (7 - col) : col;
    const file = String.fromCharCode(97 + actualCol); // a-h
    const rank = 8 - actualRow; // 8-1
    return file + rank;
  };

  // Handle square click
  const handleSquareClick = async (row, col) => {
    // Don't allow moves if game is over
    if (isCheckmate || isStalemate) {
      return;
    }
    
    const square = squareToNotation(row, col);
    // Get the actual board position accounting for perspective
    const actualRow = playingAs === 'black' ? (7 - row) : row;
    const actualCol = playingAs === 'black' ? (7 - col) : col;
    const piece = board[actualRow] && board[actualRow][actualCol];
    
    console.log(`Clicked square: ${square}, piece: ${piece}`);
    
    // If we have a selected square and this is a legal move, make the move
    if (selectedSquare && legalMoves.some(move => move.to === square)) {
      try {
        console.log(`Moving from ${selectedSquare} to ${square}`);
        
        // Make the move
        const response = await chessApiService.makeMove(selectedSquare, square);
        
        if (response.success) {
          console.log('Move successful:', response);
          
          // Update game state from response
          const newState = response.state;
          setBoard(fenToBoard(newState.fen));
          setTurn(newState.turn);
          setMoveHistory(newState.move_history || []);
          setIsCheck(newState.is_check);
          setIsCheckmate(newState.is_checkmate);
          setIsStalemate(newState.is_stalemate);
          
          if (newState.last_move) {
            setLastMove(newState.last_move);
          }
          
          // Clear selection
          setSelectedSquare(null);
          setLegalMoves([]);
          
          // Show game status
          if (newState.is_checkmate) {
            // The player who just moved (opposite of current turn) wins
            setError(`Checkmate! ${newState.turn === 'black' ? 'White' : 'Black'} wins!`);
            // Checkmate alert persists until new game
          } else if (newState.is_stalemate) {
            setError('Stalemate! Game is a draw.');
            // Stalemate alert persists until new game
          } else if (newState.is_check) {
            setError('Check!');
            // Check alert stays until check is resolved
          }
        }
      } catch (err) {
        console.error('Move failed:', err);
        setError('Invalid move');
        setTimeout(() => setError(null), 2000);
        
        // Clear selection on error
        setSelectedSquare(null);
        setLegalMoves([]);
      }
    } 
    // If clicking on a piece, select it
    else if (piece) {
      // Check if it's the right color's turn
      const isWhitePiece = piece === piece.toUpperCase();
      const pieceColor = isWhitePiece ? 'white' : 'black';
      
      if (pieceColor !== turn) {
        setError(`It's ${turn}'s turn!`);
        setTimeout(() => setError(null), 2000);
        return;
      }
      
      console.log(`Selecting piece at ${square}`);
      setSelectedSquare(square);
      
      // Get legal moves for this piece
      const moves = await getLegalMoves(square);
      console.log('Legal moves:', moves);
      setLegalMoves(moves);
    } 
    // Clicking on empty square or wrong color - deselect
    else {
      setSelectedSquare(null);
      setLegalMoves([]);
    }
  };

  // Reset the game
  const resetGame = async () => {
    try {
      await chessApiService.resetGame();
      await loadGame();
      setSelectedSquare(null);
      setLegalMoves([]);
      setError(null); // Clear any game-ending alerts (checkmate/stalemate)
      setLastMove(null); // Clear previous move highlights
      setChatHistory([]); // Clear coach chat history
      stopCurrentAudio(); // Stop any playing audio
      // Don't reset playingAs - let player keep their perspective choice
    } catch (err) {
      console.error('Failed to reset game:', err);
      setError('Failed to reset game');
      setTimeout(() => setError(null), 3000);
    }
  };

  // Render a chess piece
  const renderPiece = (piece) => {
    if (!piece) return null;
    const PieceComponent = ChessPieces[piece];
    return PieceComponent ? <PieceComponent /> : piece;
  };

  // Check if square is selected
  const isSelectedSquare = (row, col) => {
    const square = squareToNotation(row, col);
    return selectedSquare === square;
  };
  
  // Handle color selection
  const handleColorSelect = (color) => {
    if (moveHistory.length === 0) {
      setPlayingAs(color);
    }
  };

  // Check if square is a legal move
  const isLegalMoveSquare = (row, col) => {
    const square = squareToNotation(row, col);
    return legalMoves.some(move => move.to === square);
  };

  // Check if square is part of last move
  const isLastMoveSquare = (row, col) => {
    if (!lastMove) return false;
    const square = squareToNotation(row, col);
    return square === lastMove.from || square === lastMove.to;
  };
  
  // Stop any currently playing audio
  const stopCurrentAudio = () => {
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current = null;
    }
    // Also stop browser TTS
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
  };
  
  // Play audio response with proper cleanup
  const playAudioResponse = (base64Audio, fallbackText) => {
    if (!voiceEnabled) return;
    
    // Stop any current audio
    stopCurrentAudio();
    
    if (base64Audio) {
      try {
        console.log('Playing audio response, base64 length:', base64Audio.length);
        const audioData = atob(base64Audio);
        const audioArray = new Uint8Array(audioData.length);
        for (let i = 0; i < audioData.length; i++) {
          audioArray[i] = audioData.charCodeAt(i);
        }
        const audioBlob = new Blob([audioArray], { type: 'audio/wav' });
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        
        currentAudioRef.current = audio;
        audio.volume = 0.8;
        
        audio.onended = () => {
          console.log('Audio playback complete');
          URL.revokeObjectURL(audioUrl);
          currentAudioRef.current = null;
        };
        
        audio.onerror = () => {
          console.error('Audio playback error, falling back to browser TTS');
          URL.revokeObjectURL(audioUrl);
          currentAudioRef.current = null;
          // Fall back to browser TTS
          if ('speechSynthesis' in window && fallbackText) {
            const utterance = new SpeechSynthesisUtterance(fallbackText);
            utterance.rate = 0.9;
            utterance.pitch = 1.0;
            window.speechSynthesis.speak(utterance);
          }
        };
        
        audio.play().catch(err => {
          console.error('Failed to play audio:', err);
          currentAudioRef.current = null;
          // Fall back to browser TTS
          if ('speechSynthesis' in window && fallbackText) {
            const utterance = new SpeechSynthesisUtterance(fallbackText);
            utterance.rate = 0.9;
            utterance.pitch = 1.0;
            window.speechSynthesis.speak(utterance);
          }
        });
      } catch (err) {
        console.error('Error processing audio:', err);
        // Fall back to browser TTS
        if ('speechSynthesis' in window && fallbackText) {
          const utterance = new SpeechSynthesisUtterance(fallbackText);
          utterance.rate = 0.9;
          utterance.pitch = 1.0;
          window.speechSynthesis.speak(utterance);
        }
      }
    } else {
      // No audio response, use browser TTS
      console.log('No audio response, using browser TTS');
      if ('speechSynthesis' in window && fallbackText) {
        const utterance = new SpeechSynthesisUtterance(fallbackText);
        utterance.rate = 0.9;
        utterance.pitch = 1.0;
        window.speechSynthesis.speak(utterance);
      }
    }
  };

  // Start recording audio
  const startRecording = async () => {
    try {
      // Request microphone permission
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 44100
        } 
      });
      
      // Check for supported MIME types
      let mimeType = 'audio/webm';
      if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
        mimeType = 'audio/webm;codecs=opus';
      } else if (MediaRecorder.isTypeSupported('audio/webm')) {
        mimeType = 'audio/webm';
      } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
        mimeType = 'audio/mp4';
      }
      
      console.log('Using audio format:', mimeType);
      
      const options = { 
        mimeType: mimeType,
        audioBitsPerSecond: 128000
      };
      
      const mediaRecorder = new MediaRecorder(stream, options);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
        console.log('Audio blob created, size:', audioBlob.size, 'type:', audioBlob.type);
        
        // Stop all tracks to release microphone
        stream.getTracks().forEach(track => track.stop());
        
        // Send audio to coach
        await sendAudioToCoach(audioBlob);
      };
      
      mediaRecorder.onerror = (event) => {
        console.error('MediaRecorder error:', event);
        setChatHistory(prev => [...prev, { type: 'coach', message: 'Recording error. Please try again.' }]);
        stream.getTracks().forEach(track => track.stop());
        setIsRecording(false);
      };

      // Start recording
      mediaRecorder.start(100); // Collect data every 100ms
      setIsRecording(true);
      console.log('Recording started');
      
      // Visual feedback
      setChatHistory(prev => [...prev, { type: 'system', message: 'Listening... (speak now)' }]);
      
      // Auto-stop after 10 seconds (increased from 7)
      setTimeout(() => {
        if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
          console.log('Auto-stopping recording after 10 seconds');
          stopRecording();
        }
      }, 10000);
    } catch (err) {
      console.error('Failed to start recording:', err);
      
      // More specific error messages
      let errorMessage = 'Could not access microphone. ';
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        errorMessage += 'Please allow microphone access in your browser settings.';
      } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
        errorMessage += 'No microphone found. Please connect a microphone.';
      } else if (err.name === 'NotReadableError' || err.name === 'TrackStartError') {
        errorMessage += 'Microphone is in use by another application.';
      } else {
        errorMessage += err.message || 'Unknown error occurred.';
      }
      
      setChatHistory(prev => [...prev, { type: 'coach', message: errorMessage }]);
    }
  };

  // Stop recording
  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      console.log('Stopping recording');
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      
      // Remove the listening message
      setChatHistory(prev => prev.filter(msg => msg.type !== 'system'));
    }
  };

  // Send audio to coach endpoint
  const sendAudioToCoach = async (audioBlob) => {
    try {
      // Check if blob is valid
      if (!audioBlob || audioBlob.size === 0) {
        console.error('Invalid audio blob');
        setChatHistory(prev => [...prev, { type: 'coach', message: 'No audio recorded. Please try again.' }]);
        return;
      }
      
      console.log('Sending audio to backend, size:', audioBlob.size);
      
      const formData = new FormData();
      // Use appropriate extension based on MIME type
      const extension = audioBlob.type.includes('mp4') ? 'mp4' : 'webm';
      formData.append('audio', audioBlob, `recording.${extension}`);

      const response = await fetch('http://localhost:9247/coach/audio', {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const result = await response.json();
      console.log('Coach response:', result);
      
      // ALWAYS show transcription if we have it
      if (result.transcription) {
        // Add transcribed message to chat as user message
        setChatHistory(prev => [...prev, { type: 'user', message: `🎤 ${result.transcription}` }]);
      }
      
      // Handle coach response
      if (result.success && result.message) {
        // Add coach response to chat
        setChatHistory(prev => [...prev, { type: 'coach', message: result.message }]);
        
        // Play audio response - with browser fallback
        if (result.audio_response) {
          playAudioResponse(result.audio_response, result.message);
        } else if (voiceEnabled) {
          // No audio from backend - use browser TTS
          console.log('Using browser TTS fallback');
          if ('speechSynthesis' in window) {
            const utterance = new SpeechSynthesisUtterance(result.message);
            utterance.rate = 0.9;
            utterance.pitch = 1.0;
            window.speechSynthesis.speak(utterance);
          }
        }
      } else {
        // If we couldn't transcribe at all
        if (!result.transcription) {
          setChatHistory(prev => [...prev, { type: 'coach', message: 'Could not understand the audio. Please try again.' }]);
        } else if (!result.success) {
          // We transcribed but processing failed
          setChatHistory(prev => [...prev, { type: 'coach', message: result.message || 'Failed to process command' }]);
        }
      }
      
    } catch (err) {
      console.error('Failed to send audio:', err);
      setChatHistory(prev => [...prev, { type: 'coach', message: 'Failed to connect to coach. Please try again.' }]);
    }
  };

  // Send text command to coach
  const sendTextToCoach = async () => {
    const inputText = coachTextInput.trim();
    if (!inputText) return;
    
    // Add user message to chat history
    setChatHistory(prev => [...prev, { type: 'user', message: inputText }]);
    setCoachTextInput('');
    
    try {
      const response = await fetch('http://localhost:9247/coach/text', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ text: inputText })
      });

      const result = await response.json();
      
      if (result.success) {
        // Add coach response to chat history
        setChatHistory(prev => [...prev, { type: 'coach', message: result.message }]);
        
        // Play audio response with fallback
        if (result.audio_response) {
          playAudioResponse(result.audio_response, result.message);
        } else if (voiceEnabled) {
          // Browser TTS fallback
          console.log('Using browser TTS fallback');
          if ('speechSynthesis' in window) {
            const utterance = new SpeechSynthesisUtterance(result.message);
            utterance.rate = 0.9;
            utterance.pitch = 1.0;
            window.speechSynthesis.speak(utterance);
          }
        }
      } else {
        setChatHistory(prev => [...prev, { type: 'coach', message: result.message || 'Failed to process command' }]);
      }
      
    } catch (err) {
      console.error('Failed to send text:', err);
      setChatHistory(prev => [...prev, { type: 'coach', message: 'Failed to connect to coach. Please try again.' }]);
    }
  };

  // Loading screen
  if (loading) {
    return (
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        alignItems: 'center', 
        minHeight: '100vh',
        backgroundColor: '#f5f5f0'
      }}>
        <div style={{ fontSize: '24px', color: '#5d4037' }}>
          Loading Chess Board...
        </div>
      </div>
    );
  }

  return (
    <>
      <style jsx>{`
        @keyframes pulse {
          0% {
            transform: scale(1);
          }
          50% {
            transform: scale(1.02);
          }
          100% {
            transform: scale(1);
          }
        }
      `}</style>
      <div style={{ 
        display: 'flex', 
        flexDirection: isMobile ? 'column' : 'row',
        justifyContent: 'center', 
        alignItems: 'flex-start',
        gap: isMobile ? '20px' : '40px',
        padding: isMobile ? '20px' : '40px',
        minHeight: '100vh',
        backgroundColor: '#f5f5f0',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
      }}>
      
      {/* Coach Chat Panel - Left Side */}
      {!isMobile && (
        <div style={{
          width: '300px',
          height: '600px',
          backgroundColor: 'white',
          borderRadius: '8px',
          border: '2px solid #8d6e63',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
        }}>
          {/* Chat Header */}
          <div style={{
            padding: '15px',
            borderBottom: '1px solid #e0e0e0',
            backgroundColor: '#8d6e63',
            color: 'white',
            borderRadius: '6px 6px 0 0',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 600 }}>
              Chess Mentor
            </h3>
            <button
              onClick={() => setVoiceEnabled(!voiceEnabled)}
              style={{
                backgroundColor: 'transparent',
                border: '1px solid white',
                borderRadius: '4px',
                padding: '4px 8px',
                color: 'white',
                fontSize: '12px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '4px'
              }}
              title={voiceEnabled ? 'Disable voice output' : 'Enable voice output'}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="white" xmlns="http://www.w3.org/2000/svg">
                {voiceEnabled ? (
                  <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
                ) : (
                  <>
                    <path d="M3 9v6h4l5 5V4L7 9H3z"/>
                    <path d="M16.5 12l-2.5-2.5v5z" stroke="white" strokeWidth="2" strokeLinecap="round"/>
                    <path d="M19 9.5l-5 5" stroke="white" strokeWidth="2" strokeLinecap="round"/>
                  </>
                )}
              </svg>
              {voiceEnabled ? 'Voice On' : 'Voice Off'}
            </button>
          </div>
          
          {/* Chat Messages */}
          <div style={{
            flex: 1,
            overflowY: 'auto',
            padding: '15px',
            display: 'flex',
            flexDirection: 'column',
            gap: '10px'
          }}>
            {/* Always show welcome message at the top */}
            <div style={{
              padding: '15px',
              backgroundColor: '#f5f5f0',
              borderRadius: '12px',
              fontSize: '13px',
              lineHeight: '1.6',
              color: '#5d4037',
              marginTop: '10px',
              borderLeft: '4px solid #8d6e63'
            }}>
              <div style={{ fontWeight: 'bold', marginBottom: '10px' }}>
                Welcome! I'm your Chess Mentor
              </div>
              <div style={{ marginBottom: '8px' }}>I can help you with:</div>
              <div style={{ marginLeft: '10px' }}>
                <div>• <strong>Move pieces:</strong> "Move e2 to e4" or "Play Nf3"</div>
                <div>• <strong>Get hints:</strong> "Give me a hint" or "What's the best move?"</div>
                <div>• <strong>Analyze:</strong> "Analyze this position" or "Who's winning?"</div>
                <div>• <strong>Learn:</strong> "Explain castling" or "What's a pin?"</div>
                <div>• <strong>General help:</strong> "How do I improve?" or "What's my strategy?"</div>
              </div>
              <div style={{ marginTop: '10px', fontSize: '12px', fontStyle: 'italic' }}>
                Type your question or click the mic to speak!
              </div>
            </div>
            {chatHistory.map((msg, idx) => {
              // Handle system messages (like listening indicator)
              if (msg.type === 'system') {
                return (
                  <div key={idx} style={{
                    display: 'flex',
                    justifyContent: 'center',
                    margin: '10px 0'
                  }}>
                    <div style={{
                      padding: '6px 12px',
                      backgroundColor: '#fff3cd',
                      color: '#856404',
                      borderRadius: '15px',
                      fontSize: '12px',
                      fontStyle: 'italic'
                    }}>
                      {msg.message}
                    </div>
                  </div>
                );
              }
              
              // Regular user/coach messages
              return (
                <div key={idx} style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: msg.type === 'user' ? 'flex-end' : 'flex-start'
                }}>
                  <div style={{
                    fontSize: '11px',
                    color: '#8d6e63',
                    marginBottom: '2px',
                    fontWeight: 600
                  }}>
                    {msg.type === 'user' ? 'You' : 'Coach'}
                  </div>
                  <div style={{
                    maxWidth: '80%',
                    padding: '8px 12px',
                    borderRadius: '12px',
                    backgroundColor: msg.type === 'user' ? '#8d6e63' : '#f5f5f0',
                    color: msg.type === 'user' ? 'white' : '#333',
                    fontSize: '14px',
                    lineHeight: '1.4'
                  }}>
                    {msg.message}
                  </div>
                </div>
              );
            })}
            <div ref={chatEndRef} />
          </div>
          
          {/* Chat Input Area */}
          <div style={{
            padding: '15px',
            borderTop: '1px solid #e0e0e0',
            display: 'flex',
            gap: '8px'
          }}>
            <input
              type="text"
              value={coachTextInput}
              onChange={(e) => setCoachTextInput(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter') {
                  sendTextToCoach();
                }
              }}
              placeholder="Ask the coach..."
              style={{
                flex: 1,
                padding: '8px 12px',
                border: '1px solid #ddd',
                borderRadius: '20px',
                fontSize: '14px',
                outline: 'none'
              }}
            />
            <button
              onClick={isRecording ? stopRecording : startRecording}
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                backgroundColor: isRecording ? '#dc3545' : '#8d6e63',
                color: 'white',
                border: 'none',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'all 0.2s'
              }}
              title={isRecording ? 'Stop recording' : 'Voice input'}
            >
              {isRecording ? (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="white" xmlns="http://www.w3.org/2000/svg">
                  <rect x="6" y="6" width="12" height="12" rx="1"/>
                </svg>
              ) : (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="white" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 2C10.9 2 10 2.9 10 4V12C10 13.1 10.9 14 12 14C13.1 14 14 13.1 14 12V4C14 2.9 13.1 2 12 2Z"/>
                  <path d="M17 11V12C17 14.76 14.76 17 12 17C9.24 17 7 14.76 7 12V11H5V12C5 15.53 7.61 18.43 11 18.92V22H13V18.92C16.39 18.43 19 15.53 19 12V11H17Z"/>
                </svg>
              )}
            </button>
          </div>
        </div>
      )}
      
      {/* Mobile Chat Panel - Above board on mobile */}
      {isMobile && (
        <div style={{
          width: '100%',
          maxWidth: '400px',
          height: '300px',
          backgroundColor: 'white',
          borderRadius: '8px',
          border: '2px solid #8d6e63',
          display: 'flex',
          flexDirection: 'column',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
          marginBottom: '20px'
        }}>
          {/* Chat Header */}
          <div style={{
            padding: '12px',
            borderBottom: '1px solid #e0e0e0',
            backgroundColor: '#8d6e63',
            color: 'white',
            borderRadius: '6px 6px 0 0'
          }}>
            <h3 style={{ margin: 0, fontSize: '14px', fontWeight: 600 }}>
              Chess Mentor
            </h3>
          </div>
          
          {/* Chat Messages */}
          <div style={{
            flex: 1,
            overflowY: 'auto',
            padding: '12px',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px'
          }}>
            {/* Always show welcome message at the top */}
            <div style={{
              padding: '12px',
              backgroundColor: '#f5f5f0',
              borderRadius: '10px',
              fontSize: '12px',
              lineHeight: '1.5',
              color: '#5d4037',
              borderLeft: '3px solid #8d6e63'
            }}>
              <div style={{ fontWeight: 'bold', marginBottom: '8px' }}>
                Welcome! I'm your Chess Mentor
              </div>
              <div style={{ fontSize: '11px' }}>
                <div>• Move: "Move e2 to e4"</div>
                <div>• Hint: "Give me a hint"</div>
                <div>• Analyze: "Analyze position"</div>
                <div>• Learn: "Explain castling"</div>
              </div>
            </div>
            {chatHistory.map((msg, idx) => {
              // Handle system messages
              if (msg.type === 'system') {
                return (
                  <div key={idx} style={{
                    display: 'flex',
                    justifyContent: 'center',
                    margin: '8px 0'
                  }}>
                    <div style={{
                      padding: '4px 10px',
                      backgroundColor: '#fff3cd',
                      color: '#856404',
                      borderRadius: '12px',
                      fontSize: '11px',
                      fontStyle: 'italic'
                    }}>
                      {msg.message}
                    </div>
                  </div>
                );
              }
              
              // Regular messages
              return (
                <div key={idx} style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: msg.type === 'user' ? 'flex-end' : 'flex-start'
                }}>
                  <div style={{
                    fontSize: '10px',
                    color: '#8d6e63',
                    marginBottom: '2px',
                    fontWeight: 600
                  }}>
                    {msg.type === 'user' ? 'You' : 'Coach'}
                  </div>
                  <div style={{
                    maxWidth: '75%',
                    padding: '6px 10px',
                    borderRadius: '10px',
                    backgroundColor: msg.type === 'user' ? '#8d6e63' : '#f5f5f0',
                    color: msg.type === 'user' ? 'white' : '#333',
                    fontSize: '13px',
                    lineHeight: '1.3'
                  }}>
                    {msg.message}
                  </div>
                </div>
              );
            })}
            <div ref={chatEndRef} />
          </div>
          
          {/* Chat Input Area */}
          <div style={{
            padding: '10px',
            borderTop: '1px solid #e0e0e0',
            display: 'flex',
            gap: '6px'
          }}>
            <input
              type="text"
              value={coachTextInput}
              onChange={(e) => setCoachTextInput(e.target.value)}
              onKeyPress={(e) => {
                if (e.key === 'Enter') {
                  sendTextToCoach();
                }
              }}
              placeholder="Ask the coach..."
              style={{
                flex: 1,
                padding: '6px 10px',
                border: '1px solid #ddd',
                borderRadius: '15px',
                fontSize: '13px',
                outline: 'none'
              }}
            />
            <button
              onClick={isRecording ? stopRecording : startRecording}
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                backgroundColor: isRecording ? '#dc3545' : '#8d6e63',
                color: 'white',
                border: 'none',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                transition: 'all 0.2s'
              }}
              title={isRecording ? 'Stop recording' : 'Voice input'}
            >
              {isRecording ? (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="white" xmlns="http://www.w3.org/2000/svg">
                  <rect x="6" y="6" width="12" height="12" rx="1"/>
                </svg>
              ) : (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="white" xmlns="http://www.w3.org/2000/svg">
                  <path d="M12 2C10.9 2 10 2.9 10 4V12C10 13.1 10.9 14 12 14C13.1 14 14 13.1 14 12V4C14 2.9 13.1 2 12 2Z"/>
                  <path d="M17 11V12C17 14.76 14.76 17 12 17C9.24 17 7 14.76 7 12V11H5V12C5 15.53 7.61 18.43 11 18.92V22H13V18.92C16.39 18.43 19 15.53 19 12V11H17Z"/>
                </svg>
              )}
            </button>
          </div>
        </div>
      )}
      
      {/* Main Board Section with coordinates */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: '10px'
      }}>
        {/* Column coordinates at top */}
        <div style={{ 
          display: 'flex', 
          paddingLeft: '30px',
          gap: '0'
        }}>
          {(playingAs === 'black' ? ['h', 'g', 'f', 'e', 'd', 'c', 'b', 'a'] : ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']).map(letter => (
            <div key={letter} style={{
              width: isMobile ? '45px' : '70px',
              textAlign: 'center',
              color: '#8d6e63',
              fontSize: isMobile ? '12px' : '14px',
              fontWeight: 'bold'
            }}>
              {letter}
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          {/* Row coordinates on left */}
          <div style={{ 
            display: 'flex', 
            flexDirection: 'column',
            justifyContent: 'space-around',
            paddingTop: '0'
          }}>
            {(playingAs === 'black' ? [1, 2, 3, 4, 5, 6, 7, 8] : [8, 7, 6, 5, 4, 3, 2, 1]).map(num => (
              <div key={num} style={{
                height: isMobile ? '45px' : '70px',
                display: 'flex',
                alignItems: 'center',
                color: '#8d6e63',
                fontSize: isMobile ? '12px' : '14px',
                fontWeight: 'bold'
              }}>
                {num}
              </div>
            ))}
          </div>

          {/* Chess Board */}
          <div style={{
            border: '3px solid #8d6e63',
            borderRadius: '4px',
            overflow: 'hidden',
            boxShadow: '0 4px 8px rgba(0,0,0,0.15)'
          }}>
            {board.map((row, rowIndex) => {
              // Flip the board display when playing as black
              const displayRow = playingAs === 'black' ? (7 - rowIndex) : rowIndex;
              return (
                <div key={rowIndex} style={{ display: 'flex' }}>
                  {row.map((piece, colIndex) => {
                    const displayCol = playingAs === 'black' ? (7 - colIndex) : colIndex;
                    const actualPiece = board[displayRow][displayCol];
                    const isLight = (rowIndex + colIndex) % 2 === 0;
                    const isSelected = isSelectedSquare(rowIndex, colIndex);
                    const isLegalMove = isLegalMoveSquare(rowIndex, colIndex);
                    const isLastMove = isLastMoveSquare(rowIndex, colIndex);
                    
                    return (
                      <div
                        key={`${rowIndex}-${colIndex}`}
                        onClick={() => handleSquareClick(rowIndex, colIndex)}
                        style={{
                        width: isMobile ? '45px' : '70px',
                        height: isMobile ? '45px' : '70px',
                        backgroundColor: 
                          isSelected ? '#ffeb3b' :  // Yellow for selected
                          isLegalMove ? (isLight ? '#90ee90' : '#7dd87d') :  // Green for legal moves
                          isLastMove ? (isLight ? '#f0e68c' : '#daa520') :  // Gold for last move
                          isLight ? '#f0d9b5' : '#b58863',  // Normal brown squares
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        cursor: (isCheckmate || isStalemate) ? 'not-allowed' : 'pointer',
                        userSelect: 'none',
                        position: 'relative',
                        transition: 'background-color 0.2s ease'
                      }}
                    >
                      {renderPiece(actualPiece)}
                      
                      {/* Dot for empty legal move squares */}
                      {isLegalMove && !actualPiece && (
                        <div style={{
                          width: '14px',
                          height: '14px',
                          backgroundColor: 'rgba(0, 0, 0, 0.3)',
                          borderRadius: '50%',
                          position: 'absolute'
                        }} />
                      )}
                      
                      {/* Red dot for capture squares - positioned in top-right corner */}
                      {isLegalMove && actualPiece && (
                        <div style={{
                          width: '12px',
                          height: '12px',
                          backgroundColor: 'rgba(220, 38, 38, 0.8)',
                          borderRadius: '50%',
                          position: 'absolute',
                          top: '4px',
                          right: '4px',
                          pointerEvents: 'none'
                        }} />
                      )}
                    </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>

      </div>

      {/* Right Panel */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
        width: isMobile ? '100%' : '300px'
      }}>
        {/* Current Turn Section */}
        <div style={{
          backgroundColor: 'white',
          borderRadius: '8px',
          padding: '20px',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
        }}>
          <h3 style={{
            margin: '0 0 15px 0',
            color: '#999',
            fontSize: '12px',
            fontWeight: 'normal',
            textTransform: 'uppercase',
            letterSpacing: '1px'
          }}>
            CURRENT TURN
          </h3>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '10px',
            fontSize: '24px',
            fontWeight: 'bold',
            color: '#333'
          }}>
            {turn === 'white' ? 'White' : 'Black'}
          </div>

          
          {/* Game Status Alerts */}
          {error && (
            <div style={{
              marginTop: '15px',
              padding: isCheckmate || isStalemate ? '15px' : '10px',
              backgroundColor: isCheckmate ? '#d4edda' : 
                             isStalemate ? '#d1ecf1' :
                             isCheck ? '#fff3cd' : 
                             '#f8d7da',
              color: isCheckmate ? '#155724' : 
                    isStalemate ? '#0c5460' :
                    isCheck ? '#856404' : 
                    '#721c24',
              borderRadius: '5px',
              fontSize: isCheckmate || isStalemate ? '16px' : '14px',
              fontWeight: 'bold',
              textAlign: 'center',
              borderLeft: `4px solid ${isCheckmate ? '#28a745' : isStalemate ? '#17a2b8' : isCheck ? '#ffc107' : '#dc3545'}`,
              boxShadow: isCheckmate || isStalemate ? '0 2px 8px rgba(0,0,0,0.15)' : 'none',
              animation: isCheckmate ? 'pulse 2s infinite' : 'none'
            }}>
              {error}
              {(isCheckmate || isStalemate) && (
                <div style={{
                  marginTop: '8px',
                  fontSize: '12px',
                  fontWeight: 'normal',
                  opacity: 0.8
                }}>
                  Click "NEW GAME" to play again
                </div>
              )}
            </div>
          )}
        </div>

        {/* New Game Button */}
        <button
          onClick={resetGame}
          style={{
            padding: '15px',
            backgroundColor: (isCheckmate || isStalemate) ? '#28a745' : '#b58863',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
            fontSize: '16px',
            fontWeight: 'bold',
            textTransform: 'uppercase',
            boxShadow: (isCheckmate || isStalemate) ? '0 4px 8px rgba(40, 167, 69, 0.3)' : '0 2px 4px rgba(0,0,0,0.1)',
            transition: 'all 0.2s',
            animation: (isCheckmate || isStalemate) ? 'pulse 2s infinite' : 'none'
          }}
          onMouseOver={(e) => e.target.style.backgroundColor = (isCheckmate || isStalemate) ? '#218838' : '#8d6e63'}
          onMouseOut={(e) => e.target.style.backgroundColor = (isCheckmate || isStalemate) ? '#28a745' : '#b58863'}
        >
          NEW GAME
        </button>

        {/* Playing As Section */}
        <div style={{
          backgroundColor: 'white',
          borderRadius: '8px',
          padding: '20px',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
        }}>
          <h3 style={{
            margin: '0 0 15px 0',
            color: '#999',
            fontSize: '12px',
            fontWeight: 'normal',
            textTransform: 'uppercase',
            letterSpacing: '1px'
          }}>
            PLAYING AS
          </h3>
          {moveHistory.length === 0 && (
            <p style={{
              fontSize: '12px',
              color: '#666',
              margin: '0 0 10px 0',
              fontStyle: 'italic'
            }}>
              Choose your side before making a move
            </p>
          )}
          <div style={{
            display: 'flex',
            gap: '10px'
          }}>
            <button
              onClick={() => handleColorSelect('white')}
              disabled={moveHistory.length > 0}
              style={{
                flex: 1,
                padding: '12px',
                border: playingAs === 'white' ? '2px solid #b58863' : '2px solid #ddd',
                backgroundColor: playingAs === 'white' ? 'white' : '#f5f5f5',
                borderRadius: '6px',
                cursor: moveHistory.length > 0 ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                fontSize: '14px',
                fontWeight: playingAs === 'white' ? 'bold' : 'normal',
                color: playingAs === 'white' ? '#333' : '#999',
                transition: 'all 0.2s',
                opacity: moveHistory.length > 0 ? 0.6 : 1
              }}
              onMouseOver={(e) => {
                if (moveHistory.length === 0) {
                  e.currentTarget.style.backgroundColor = playingAs === 'white' ? '#f0d9b5' : '#e0e0e0';
                }
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.backgroundColor = playingAs === 'white' ? 'white' : '#f5f5f5';
              }}
            >
              WHITE
            </button>
            <button
              onClick={() => handleColorSelect('black')}
              disabled={moveHistory.length > 0}
              style={{
                flex: 1,
                padding: '12px',
                border: playingAs === 'black' ? '2px solid #b58863' : '2px solid #ddd',
                backgroundColor: playingAs === 'black' ? 'white' : '#f5f5f5',
                borderRadius: '6px',
                cursor: moveHistory.length > 0 ? 'not-allowed' : 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                fontSize: '14px',
                fontWeight: playingAs === 'black' ? 'bold' : 'normal',
                color: playingAs === 'black' ? '#333' : '#999',
                transition: 'all 0.2s',
                opacity: moveHistory.length > 0 ? 0.6 : 1
              }}
              onMouseOver={(e) => {
                if (moveHistory.length === 0) {
                  e.currentTarget.style.backgroundColor = playingAs === 'black' ? '#f0d9b5' : '#e0e0e0';
                }
              }}
              onMouseOut={(e) => {
                e.currentTarget.style.backgroundColor = playingAs === 'black' ? 'white' : '#f5f5f5';
              }}
            >
              BLACK
            </button>
          </div>
        </div>

        {/* Move History Panel */}
        <div style={{
          backgroundColor: 'white',
          borderRadius: '8px',
          padding: '20px',
          boxShadow: '0 2px 4px rgba(0,0,0,0.1)',
          flex: 1,
          maxHeight: isMobile ? '200px' : '400px',
          display: 'flex',
          flexDirection: 'column'
        }}>
          <h3 style={{
            margin: '0 0 15px 0',
            color: '#333',
            fontSize: '18px',
            fontWeight: 'bold'
          }}>
            Move History
          </h3>
          
          <div 
            ref={moveHistoryRef}
            style={{
              flex: 1,
              overflowY: 'auto',
              fontSize: isMobile ? '13px' : '14px',
              fontFamily: 'monospace',
              lineHeight: '1.6',
              color: '#666'
            }}
          >
            {moveHistory.length === 0 ? (
              <div style={{ 
                color: '#999', 
                fontStyle: 'normal',
                textAlign: 'center',
                marginTop: '20px',
                fontSize: '14px'
              }}>
                No moves yet. Click a piece to start!
              </div>
            ) : (
              <div>
                {moveHistory.map((move, index) => {
                  const moveNumber = Math.floor(index / 2) + 1;
                  const isWhiteMove = index % 2 === 0;
                  
                  return (
                    <span key={index}>
                      {isWhiteMove && (
                        <span style={{ color: '#666' }}>
                          {moveNumber}.{' '}
                        </span>
                      )}
                      <span style={{ 
                        fontWeight: 'bold',
                        color: '#333' 
                      }}>
                        {move}
                      </span>
                      {isWhiteMove ? '  ' : '\n'}
                    </span>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
    </>
  );
}