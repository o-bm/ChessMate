#!/usr/bin/env python3
"""
Chess Move Tracker - HSV-based Black Piece Detection
Modified for Raspberry Pi with OAK Camera and GPIO Button Control
"""

import cv2
import numpy as np
import depthai as dai
import json
import os
import time
import requests
from gpiozero import Button 


# =========================
# API Configuration
# =========================
API_IP = "10.37.101.170"  # Your laptop's IP
API_PORT = 9247           # Backend port
API_ENDPOINT = "move"     # Endpoint for chess moves
API_URL = f"http://{API_IP}:{API_PORT}/{API_ENDPOINT}"


# =========================
# Configuration
# =========================
BOARD_SIZE = 800  # Output resolution for warped board
GRID = 8

# GPIO Configuration
MOVE_BUTTON_PIN = 14  # BUTTON

# Detection parameters for black pieces using HSV
DETECTION_MARGIN = 0.10  # Use inner 80% of square

# HSV ranges for black pieces
# Black has low saturation and low value
HSV_BLACK_LOWER = np.array([0, 0, 0])      # H: any, S: 0-50, V: 0-60
HSV_BLACK_UPPER = np.array([180, 50, 60])  # Adjustable with controls

MIN_BLACK_PIXELS = 250    # Minimum black pixels to consider occupied

# State files
STATE_DIR = "chess_state"
CALIB_FILE = os.path.join(STATE_DIR, "calibration_hsv.json")

# Colors (BGR)
COLOR_GREEN = (0, 255, 0)
COLOR_RED = (0, 0, 255)
COLOR_BLUE = (255, 100, 0)
COLOR_YELLOW = (0, 255, 255)
COLOR_WHITE = (255, 255, 255)
COLOR_GRAY = (128, 128, 128)
COLOR_CYAN = (255, 255, 0)

# =========================
# Chess Notation
# =========================
def square_to_notation(row, col):
    """Convert grid position to chess notation"""
    files = "abcdefgh"
    ranks = "87654321"
    return f"{files[col]}{ranks[row]}"

# =========================
# File Operations
# =========================
def save_calibration(corners):
    """Save calibration corners"""
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(CALIB_FILE, "w") as f:
        json.dump({"corners": corners}, f)
    print(f"[SAVED] Calibration to {CALIB_FILE}")

def load_calibration():
    """Load calibration and compute homography"""
    if not os.path.exists(CALIB_FILE):
        return None
    
    with open(CALIB_FILE, "r") as f:
        data = json.load(f)
    
    corners = data.get("corners")
    if corners:
        src = np.array(corners, dtype=np.float32)
        dst = np.array([[0,0], [BOARD_SIZE-1,0], 
                       [BOARD_SIZE-1,BOARD_SIZE-1], [0,BOARD_SIZE-1]], dtype=np.float32)
        H, _ = cv2.findHomography(src, dst, cv2.RANSAC)
        return H
    return None

# =========================
# HSV-based Detection
# =========================
def detect_black_pieces_hsv(board_img, s_max=50, v_max=60, min_pixels=MIN_BLACK_PIXELS, show_mask=False):
    """
    Detect black pieces using HSV color space
    Black pieces have low saturation and low value
    Returns 8x8 occupancy grid, pixel counts, and optionally the mask
    """
    h, w = board_img.shape[:2]
    square_h = h // GRID
    square_w = w // GRID
    
    # Convert to HSV
    hsv = cv2.cvtColor(board_img, cv2.COLOR_BGR2HSV)
    
    # Create mask for black colors
    lower_black = np.array([0, 0, 0])
    upper_black = np.array([180, s_max, v_max])
    black_mask = cv2.inRange(hsv, lower_black, upper_black)
    
    # Optional: Apply morphology to clean up
    kernel = np.ones((3, 3), np.uint8)
    black_mask = cv2.morphologyEx(black_mask, cv2.MORPH_CLOSE, kernel)
    black_mask = cv2.morphologyEx(black_mask, cv2.MORPH_OPEN, kernel)
    
    occupancy = np.zeros((GRID, GRID), dtype=bool)
    pixel_counts = np.zeros((GRID, GRID), dtype=int)
    
    for row in range(GRID):
        for col in range(GRID):
            # Extract square
            y1, y2 = row * square_h, (row + 1) * square_h
            x1, x2 = col * square_w, (col + 1) * square_w
            
            # Get inner region from mask
            margin = int(min(square_h, square_w) * DETECTION_MARGIN)
            inner_mask = black_mask[y1+margin:y2-margin, x1+margin:x2-margin]
            
            if inner_mask.size > 0:
                # Count black pixels
                black_pixels = cv2.countNonZero(inner_mask)
                pixel_counts[row, col] = black_pixels
                
                # Determine occupancy
                occupancy[row, col] = black_pixels >= min_pixels
    
    if show_mask:
        return occupancy, pixel_counts, black_mask
    return occupancy, pixel_counts

def find_move(prev_state, curr_state):
    """Find move by comparing states"""
    changes = []
    for r in range(GRID):
        for c in range(GRID):
            if prev_state[r, c] != curr_state[r, c]:
                changes.append((r, c))
    
    if len(changes) != 2:
        return None, changes
    
    # Determine from and to squares
    sq1, sq2 = changes
    if prev_state[sq1] and not curr_state[sq1]:
        return (sq1, sq2), changes
    elif prev_state[sq2] and not curr_state[sq2]:
        return (sq2, sq1), changes
    else:
        return (sq2, sq1) if curr_state[sq1] else (sq1, sq2), changes

# =========================
# Visualization
# =========================
def draw_board(board_img, occupancy, pixel_counts=None, last_move=None, show_debug=False):
    """Draw board with overlays"""
    output = board_img.copy()
    h, w = output.shape[:2]
    square_h = h // GRID
    square_w = w // GRID
    
    # Draw grid and pieces
    for row in range(GRID):
        for col in range(GRID):
            x1, x2 = col * square_w, (col + 1) * square_w
            y1, y2 = row * square_h, (row + 1) * square_h
            
            # Grid lines
            cv2.rectangle(output, (x1, y1), (x2, y2), COLOR_GRAY, 1)
            
            # Square notation
            notation = square_to_notation(row, col)
            cv2.putText(output, notation, (x1 + 5, y1 + 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, COLOR_GRAY, 1)
            
            # Piece indicator
            if occupancy[row, col]:
                center = (x1 + square_w // 2, y1 + square_h // 2)
                cv2.circle(output, center, 20, COLOR_GREEN, -1)
                cv2.circle(output, center, 20, (0, 150, 0), 2)
            
            # Debug info
            if show_debug and pixel_counts is not None:
                count = pixel_counts[row, col]
                color = COLOR_GREEN if occupancy[row, col] else COLOR_RED
                cv2.putText(output, str(count), 
                           (x1 + square_w//2 - 15, y1 + square_h//2 + 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
    
    # Last move arrow
    if last_move:
        (from_r, from_c), (to_r, to_c) = last_move
        from_pt = (from_c * square_w + square_w // 2, from_r * square_h + square_h // 2)
        to_pt = (to_c * square_w + square_w // 2, to_r * square_h + square_h // 2)
        cv2.arrowedLine(output, from_pt, to_pt, COLOR_BLUE, 4, tipLength=0.2)
    
    # File and rank labels
    files = "ABCDEFGH"
    ranks = "87654321"
    
    for i in range(GRID):
        # Files (A-H)
        x = i * square_w + square_w // 2 - 10
        cv2.putText(output, files[i], (x, 25), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, COLOR_YELLOW, 2)
        cv2.putText(output, files[i], (x, h - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, COLOR_YELLOW, 2)
        
        # Ranks (1-8)
        y = i * square_h + square_h // 2 + 10
        cv2.putText(output, ranks[i], (10, y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, COLOR_YELLOW, 2)
        cv2.putText(output, ranks[i], (w - 30, y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, COLOR_YELLOW, 2)
    
    return output


## SENDING THE REQUESTT
def send_request(from_sq, to_sq):
    """Send move to backend API"""
    try:
        response = requests.post(
            API_URL,
            json={"from_sq": from_sq, "to_sq": to_sq},
            timeout=5
        )
        result = response.json()
        print(f"[API] ✓ Move sent to {API_IP}:{API_PORT} - {result['message']}")
    except Exception as e:
        print(f"[API] ✗ Error connecting to {API_IP}:{API_PORT} - {e}")


# =========================
# Main Application
# =========================
def main():
    print("\n" + "="*60)
    print("CHESS TRACKER - HSV COLOR DETECTION")
    print("Black Pieces using HSV Color Space")
    print("="*60)
    print("\nHSV DETECTION:")
    print("  Black = Low Saturation (0-50) + Low Value (0-60)")
    print("\nCONTROLS:")
    print("  C        - Calibrate (click 4 corners)")
    print("  Button   - Detect move (GPIO 14)")  # Updated control description
    print("  D        - Toggle debug (pixel counts)")
    print("  M        - Show HSV mask")
    print("  S/s      - Adjust max Saturation (+/-)")
    print("  V/v      - Adjust max Value (+/-)")
    print("  ]/[      - Adjust min pixels")
    print("  R        - Reset")
    print("  Q        - Quit")
    print("="*60 + "\n")
    
    # Initialize GPIO button
    move_button = Button(MOVE_BUTTON_PIN, pull_up=True, bounce_time=0.1)
    button_pressed_flag = False
    
    def on_button_press():
        nonlocal button_pressed_flag
        button_pressed_flag = True
        print("[BUTTON] Move detection triggered")
    
    # Set up button callback
    move_button.when_pressed = on_button_press
    print(f"[GPIO] Button initialized on GPIO {MOVE_BUTTON_PIN}")
    
    # Initialize camera pipeline (MODIFIED FOR RASPBERRY PI)
    pipeline = dai.Pipeline()
    
    # Create color camera
    cam = pipeline.createColorCamera()
    cam.setPreviewSize(1280, 720)
    cam.setInterleaved(False)
    cam.setColorOrder(dai.ColorCameraProperties.ColorOrder.BGR)
    cam.setFps(30)
    
    # Create output
    xout = pipeline.createXLinkOut()
    xout.setStreamName("video")
    cam.preview.link(xout.input)
    
    # Connect to device
    print("Connecting to OAK camera...")
    try:
        with dai.Device(pipeline) as device:
            print("Connected! Starting chess tracker...")
            
            # Get output queue
            video_q = device.getOutputQueue("video")
            
            # State
            H = load_calibration()
            calib_mode = False
            calib_clicks = []
            show_debug = False
            show_mask = False
            
            # HSV thresholds
            s_max = 50  # Max saturation for black
            v_max = 60  # Max value (brightness) for black
            min_pixels = MIN_BLACK_PIXELS
            
            # Board state
            prev_occupancy = None
            last_move = None
            move_history = []
            
            # Mouse callback for calibration
            def mouse_callback(event, x, y, flags, param):
                nonlocal calib_clicks
                if event == cv2.EVENT_LBUTTONDOWN and calib_mode and len(calib_clicks) < 4:
                    calib_clicks.append([x, y])
                    corners = ["Top-Left", "Top-Right", "Bottom-Right", "Bottom-Left"]
                    print(f"[CALIB] {corners[len(calib_clicks)-1]}: ({x}, {y})")
            
            # Windows
            cv2.namedWindow("Camera", cv2.WINDOW_NORMAL)
            cv2.setMouseCallback("Camera", mouse_callback)
            cv2.namedWindow("Board", cv2.WINDOW_NORMAL)
            
            print("Ready! Press 'C' to calibrate..." if H is None else "Calibrated! Press button to track moves.")
            
            while True:
                # Get frame
                frame = video_q.get().getCvFrame()
                cam_display = frame.copy()
                
                # Draw calibration UI
                if calib_mode:
                    for i, pt in enumerate(calib_clicks):
                        cv2.circle(cam_display, tuple(pt), 8, COLOR_YELLOW, -1)
                        cv2.putText(cam_display, str(i+1), (pt[0]+10, pt[1]-10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_YELLOW, 2)
                    
                    if len(calib_clicks) > 1:
                        cv2.polylines(cam_display, [np.array(calib_clicks, np.int32)], 
                                     len(calib_clicks) == 4, COLOR_YELLOW, 2)
                    
                    status = f"Click corner {len(calib_clicks)+1}/4"
                    cv2.putText(cam_display, status, (10, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, COLOR_YELLOW, 2)
                elif H is not None:
                    cv2.putText(cam_display, "CALIBRATED", (10, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.8, COLOR_GREEN, 2)
                
                # Show HSV thresholds and button status
                info = f"HSV: S<={s_max} V<={v_max} | Min Pixels: {min_pixels}"
                cv2.putText(cam_display, info, (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, COLOR_CYAN, 1)
                
                # Show button status
                button_status = "Button: Ready" if not button_pressed_flag else "Button: PRESSED"
                button_color = COLOR_GREEN if not button_pressed_flag else COLOR_YELLOW
                cv2.putText(cam_display, button_status, (10, 90),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, button_color, 1)
                
                cv2.imshow("Camera", cam_display)
                
                # Process calibration
                if calib_mode and len(calib_clicks) == 4:
                    src = np.array(calib_clicks, dtype=np.float32)
                    dst = np.array([[0,0], [BOARD_SIZE-1,0],
                                  [BOARD_SIZE-1,BOARD_SIZE-1], [0,BOARD_SIZE-1]], dtype=np.float32)
                    H, _ = cv2.findHomography(src, dst, cv2.RANSAC)
                    
                    if H is not None:
                        save_calibration(calib_clicks)
                        print("[SUCCESS] Calibration complete!")
                        
                        # Initial detection
                        warped = cv2.warpPerspective(frame, H, (BOARD_SIZE, BOARD_SIZE))
                        prev_occupancy, _ = detect_black_pieces_hsv(warped, s_max, v_max, min_pixels)
                        
                        # Count pieces
                        piece_count = np.sum(prev_occupancy)
                        print(f"[INFO] Detected {piece_count} black pieces")
                        
                    calib_mode = False
                    calib_clicks = []
                
                # Process board if calibrated
                if H is not None:
                    warped = cv2.warpPerspective(frame, H, (BOARD_SIZE, BOARD_SIZE))
                    
                    if show_mask:
                        occupancy, pixel_counts, mask = detect_black_pieces_hsv(warped, s_max, v_max, min_pixels, True)
                        # Show the HSV mask
                        mask_colored = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
                        cv2.imshow("HSV Mask", mask_colored)
                    else:
                        occupancy, pixel_counts = detect_black_pieces_hsv(warped, s_max, v_max, min_pixels)
                        # Safely destroy mask window if it exists
                        try:
                            if cv2.getWindowProperty("HSV Mask", cv2.WND_PROP_VISIBLE) >= 0:
                                cv2.destroyWindow("HSV Mask")
                        except:
                            pass
                    
                    board_display = draw_board(warped, occupancy, pixel_counts, last_move, show_debug)
                    cv2.imshow("Board", board_display)
                
                # Check for button press (replaces spacebar functionality)
                if button_pressed_flag:
                    button_pressed_flag = False  # Reset flag
                    
                    if H is None:
                        print("[ERROR] Calibrate first!")
                    elif prev_occupancy is None:
                        prev_occupancy = occupancy
                        print("[INFO] Initial state captured")
                    else:
                        move, changes = find_move(prev_occupancy, occupancy)
                        
                        if move:
                            (from_r, from_c), (to_r, to_c) = move
                            from_sq = square_to_notation(from_r, from_c)
                            to_sq = square_to_notation(to_r, to_c)
                            
                            move_str = f"{from_sq}-{to_sq}"
                            send_request(from_sq, to_sq)
                            move_history.append(move_str)
                            print(f"\n[MOVE {len(move_history)}] {move_str}")
                            
                            last_move = move
                            prev_occupancy = occupancy.copy()
                        else:
                            if len(changes) == 0:
                                print("[INFO] No changes")
                            else:
                                print(f"[WARNING] {len(changes)} changes (expected 2)")
                                print(f"  Changed: {[square_to_notation(r, c) for r, c in changes]}")
                
                # Handle keyboard (removed spacebar handling)
                key = cv2.waitKey(1) & 0xFF
                
                if key == ord('q'):
                    break
                
                elif key == ord('c'):
                    calib_clicks = []
                    calib_mode = True
                    print("\n[CALIBRATION] Click 4 corners: TL, TR, BR, BL")
                
                # Spacebar functionality removed - now handled by button
                
                elif key == ord('d'):
                    show_debug = not show_debug
                    print(f"[DEBUG] {'ON' if show_debug else 'OFF'}")
                
                elif key == ord('m'):
                    show_mask = not show_mask
                    print(f"[MASK] {'ON' if show_mask else 'OFF'}")
                
                elif key == ord('S'):  # Increase max saturation
                    s_max = min(255, s_max + 5)
                    print(f"[HSV] Max Saturation: {s_max}")
                
                elif key == ord('s'):  # Decrease max saturation
                    s_max = max(10, s_max - 5)
                    print(f"[HSV] Max Saturation: {s_max}")
                
                elif key == ord('V'):  # Increase max value
                    v_max = min(255, v_max + 5)
                    print(f"[HSV] Max Value: {v_max}")
                
                elif key == ord('v'):  # Decrease max value
                    v_max = max(10, v_max - 5)
                    print(f"[HSV] Max Value: {v_max}")
                
                elif key == ord(']'):
                    min_pixels = min(500, min_pixels + 25)
                    print(f"[MIN PIXELS] {min_pixels}")
                
                elif key == ord('['):
                    min_pixels = max(50, min_pixels - 25)
                    print(f"[MIN PIXELS] {min_pixels}")
                
                elif key == ord('r'):
                    H = None
                    prev_occupancy = None
                    last_move = None
                    move_history = []
                    calib_clicks = []
                    calib_mode = False
                    s_max = 50
                    v_max = 60
                    min_pixels = MIN_BLACK_PIXELS
                    button_pressed_flag = False  # Reset button flag
                    if os.path.exists(CALIB_FILE):
                        os.remove(CALIB_FILE)
                    print("[RESET] All cleared")
            
            cv2.destroyAllWindows()
            print("\n[EXIT] Goodbye!")
            
    except Exception as e:
        print(f"Error: {e}")
        print("OAK camera not working - check connection")

if __name__ == "__main__":
    main()