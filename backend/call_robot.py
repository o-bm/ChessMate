import requests
import time
import sys
import os

# Add both the chess directory and path_finder directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))  # /home/pi/chess
path_finder_dir = os.path.join(current_dir, 'path_finder')  # /home/pi/chess/path_finder

# Add path_finder to sys.path so main.py can find its local imports
sys.path.insert(0, path_finder_dir)
sys.path.insert(0, current_dir)

# Import BOTH the function AND the connect_arduino function!!! THIS WAS THE BUG
from path_finder.main import execute_chess_move, connect_arduino

API_IP = "10.37.101.170"  # Your laptop's IP
API_PORT = 9247           # Backend port
API_ENDPOINT = "robot/moves"  # Endpoint for voice commands
API_URL = f"http://{API_IP}:{API_PORT}/{API_ENDPOINT}"

processed_count = 0

print("🤖 Robot polling for moves...")
print("📍 Robot movement system initialized")

# CRITICAL: Connect to Arduino BEFORE starting the main loop!!!
connect_arduino()
print("✅ Arduino connected and ready!")

while True:
    try:
        response = requests.get(API_URL)
        moves = response.json()['moves']
        
        while processed_count < len(moves):
            move = moves[processed_count]
            
            if move['is_white'] or move['source'] == 'coach':
                if move['is_white']:
                    print(f"\n⚪ White move #{processed_count + 1}")
                else:
                    print(f"\n⚫ Black move #{processed_count + 1}")
                print(f"  from={move['from']}, to={move['to']}, " +
                      f"capture={move['is_capture']}, " +
                      f"promotion={move['is_promotion']}, " +
                      f"castle={move['is_castle']}")
                
                # Execute the chess move using the path_finder module
                promotion_piece = 'Q' if move.get('is_promotion') else None
                
                success = execute_chess_move(
                    from_square=move['from'],
                    to_square=move['to'],
                    is_capture=move['is_capture'],
                    promotion_piece=promotion_piece,
                    is_castling=move['is_castle']
                )
                
                if success:
                    print(f"✅ Move executed successfully!")
                else:
                    print(f"❌ Failed to execute move!")
            
            processed_count += 1
        
        time.sleep(1)
        
    except KeyboardInterrupt:
        print("\n👋 Shutting down robot controller...")
        break
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(1)