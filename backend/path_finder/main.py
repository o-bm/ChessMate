#!/usr/bin/env python3
"""
Chess Notation to Physical Movement Converter - Terminal Interface
"""

import serial
import time
from chess_parser import ChessNotationParser
from coordinate_converter import CoordinateConverter
from path_planner import PathPlanner

# Initialize components
parser = ChessNotationParser()
converter = CoordinateConverter()
planner = PathPlanner()

ARDUINO_PORT = '/dev/serial/by-id/usb-Arduino_Srl_Arduino_Uno_8543833393535110F0D1-if00' 
ARDUINO_BAUDRATE = 115200
arduino = None


def connect_arduino():
    """Connect to Arduino via serial port."""
    global arduino
    try:
        arduino = serial.Serial(ARDUINO_PORT, ARDUINO_BAUDRATE, timeout=1)
        time.sleep(2)  # Wait for Arduino reset
        print(f"✅ Connected to Arduino on {ARDUINO_PORT}")
        return arduino
    except serial.SerialException as e:
        print(f"⚠️ Failed to connect to Arduino: {e}")
        print("Continuing in simulation mode...")
        return None


def send_command(arduino_connection, command: str) -> bool:
    """Send a single command to Arduino and wait for confirmation."""
    if arduino_connection is None:
        print(f"SIMULATION: {command}")
        return True
    
    try:
        arduino_connection.write((command + "\n").encode())
        
        while True:
            if arduino_connection.in_waiting > 0:
                response = arduino_connection.readline().decode().strip()
                
                if response.startswith("Done"):
                    return True
                elif response.startswith("Error"):
                    print(f"Arduino error: {response}")
                    return False
        
    except Exception as e:
        print(f"Error sending command '{command}': {e}")
        return False


def execute_chess_move(from_square: str, to_square: str, is_capture: bool = False, 
                      promotion_piece: str = None, is_castling: bool = False) -> bool:
    """
    Execute a chess move including special moves.
    """
    try:
        # Auto-detect castling if not specified
        if not is_castling:
            is_castling = planner._is_castling_move(from_square, to_square)
        
        # Handle promotion
        if promotion_piece:
            commands = planner.plan_path(from_square, to_square, is_capture, True)
            commands.extend(_plan_promotion_sequence(to_square, promotion_piece))
        else:
            commands = planner.plan_path(from_square, to_square, is_capture, True)
        
        # Send commands to Arduino
        for i, cmd in enumerate(commands, 1):
            if not send_command(arduino, cmd):
                return False
        
        return True
        
    except Exception as e:
        print(f"Error executing move: {e}")
        return False


def _plan_promotion_sequence(promotion_square: str, promotion_piece: str) -> list:
    """Plan the sequence to replace a promoted pawn with the chosen piece."""
    commands = []
    
    promotion_coords = converter.chess_to_grid(promotion_square, use_channel=False)
    
    commands.extend(planner._plan_edge_movement(planner.home_position, promotion_coords, carrying_piece=False))
    commands.append("raise")
    
    temp_discard = converter.get_next_discard_position(True)
    commands.extend(planner._plan_edge_movement(promotion_coords, temp_discard, carrying_piece=True))
    commands.append("lower")
    
    commands.append("home")
    commands.append(f"PROMOTE:{promotion_piece}")
    
    commands.extend(planner._plan_edge_movement(planner.home_position, promotion_coords, carrying_piece=False))
    commands.append("raise")
    commands.extend(planner._plan_edge_movement(planner.home_position, promotion_coords, carrying_piece=True))
    commands.append("lower")
    
    return commands


def simple_move_interface():
    """Simple interface that asks for 4 inputs and executes a single move."""
    print("🏁 CHESS MOVEMENT SYSTEM - SIMPLE MOVE INTERFACE")
    print("=" * 60)
    
    try:
        from_square = input("From square (e.g., e2): ").strip().lower()
        to_square = input("To square (e.g., e4): ").strip().lower()
        
        capture_input = input("Is this a capture? (y/n): ").strip().lower()
        is_capture = capture_input in ['y', 'yes', 'true', '1']
        
        castle_input = input("Is this castling? (y/n): ").strip().lower()
        is_castling = castle_input in ['y', 'yes', 'true', '1']
        
        success = execute_chess_move(from_square, to_square, is_capture, None, is_castling)
        
        if success:
            print(f"✅ Move {from_square}→{to_square} executed successfully!")
        else:
            print(f"❌ Move {from_square}→{to_square} failed!")
            
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    print("Starting Chess Movement System...")
    
    connect_arduino()
    
    try:
        print("\nChoose interface:")
        print("1. Simple move interface (4 inputs)")
        print("2. Interactive chess interface (full game)")
        choice = input("Enter choice (1 or 2): ").strip()
        
        if choice == "1":
            simple_move_interface()
        else:
            print("Interactive interface not implemented")
            simple_move_interface()
    finally:
        if arduino:
            arduino.close()
            print("Arduino connection closed")