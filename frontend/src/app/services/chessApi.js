const API_BASE = process.env.NEXT_PUBLIC_CHESS_API || "http://localhost:9247";

async function jsonFetch(url, options = {}) {
  try {
    console.log(`Making request to: ${url}`, options);
    
    const config = {
      headers: { "Content-Type": "application/json" },
      ...options
    };

    const res = await fetch(url, config);
    
    if (!res.ok) {
      let errorMessage = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errorData = await res.json();
        errorMessage = errorData?.detail || errorMessage;
      } catch (e) {
        // If we can't parse JSON, use the HTTP status
      }
      throw new Error(errorMessage);
    }

    const data = await res.json();
    console.log(`Response from ${url}:`, data);
    return data;
    
  } catch (error) {
    console.error(`Request failed for ${url}:`, error);
    
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      throw new Error('Cannot connect to chess server. Make sure it\'s running on http://localhost:9247');
    }
    
    throw error;
  }
}

const chessApiService = {
  async getGameState() {
    return jsonFetch(`${API_BASE}/game`);
  },

  async configureGame(onlinePlayerColor) {
    return jsonFetch(`${API_BASE}/configure`, {
      method: 'POST',
      body: JSON.stringify({
        online_player_color: onlinePlayerColor
      })
    });
  },

  async getConfig() {
    return jsonFetch(`${API_BASE}/config`);
  },
  
  async makeMove(from, to, promotion = null, source = 'web') {
    const url = source === 'web' 
      ? `${API_BASE}/move?source=web`
      : `${API_BASE}/move?source=${source}`;
    
    return jsonFetch(url, {
      method: "POST",
      body: JSON.stringify({ from_sq: from, to_sq: to, promotion }),
    });
  },
  
  async getLegalMoves(square) {
    return jsonFetch(`${API_BASE}/legal-moves`, {
      method: "POST",
      body: JSON.stringify({ square }),
    });
  },
  
  async resetGame() {
    return jsonFetch(`${API_BASE}/reset`, { 
      method: "POST",
      body: JSON.stringify({}) // Add empty body for POST request
    });
  },
};

export default chessApiService;