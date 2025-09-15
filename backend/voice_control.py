#!/usr/bin/env python3
from gpiozero import Button
from signal import pause
import threading, pyaudio, wave, time
import os, sys
from contextlib import contextmanager
import requests
import io
import base64
import subprocess

# =========================
# API Configuration
# =========================
API_IP = "10.37.101.170"  # Your laptop's IP
API_PORT = 9247           # Backend port
API_ENDPOINT = "coach/audio"  # Endpoint for voice commands
API_URL = f"http://{API_IP}:{API_PORT}/{API_ENDPOINT}"

# Context manager to suppress ALSA warnings
@contextmanager
def suppress_alsa_warnings():
    """Suppress ALSA lib warnings"""
    devnull = os.open(os.devnull, os.O_WRONLY)
    old_stderr = os.dup(2)
    sys.stderr.flush()
    os.dup2(devnull, 2)
    os.close(devnull)
    try:
        yield
    finally:
        os.dup2(old_stderr, 2)
        os.close(old_stderr)

button = Button(17, pull_up=True, bounce_time=0.05)
timer = None
recording = False
frames = []

def record():
    global frames, recording
    with suppress_alsa_warnings():
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, 
                       input=True, frames_per_buffer=1024)
    
    frames = []
    while recording:
        frames.append(stream.read(1024, exception_on_overflow=False))
    
    stream.stop_stream()
    stream.close()
    with suppress_alsa_warnings():
        p.terminate()

def play_audio(wav_file):
    """Play WAV file on Raspberry Pi"""
    # Method 1: Using aplay (most common on Pi)
    try:
        with suppress_alsa_warnings():
            subprocess.run(['aplay', wav_file], check=True, 
                         stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    except:
        # Method 2: Using pygame
        try:
            import pygame
            pygame.mixer.init()
            pygame.mixer.music.load(wav_file)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
        except:
            print(f"Audio saved to {wav_file} - please play manually")

def speak_text(text):
    """Fallback TTS using espeak"""
    try:
        subprocess.run(['espeak', text], check=True, 
                      stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    except:
        print(f"Install espeak for TTS: sudo apt-get install espeak")
        print(f"Text response: {text}")

def send_voice_and_handle_response(audio_data):
    """Send voice command and play the coach's response"""
    try:
        # Create WAV file in memory
        wav_buffer = io.BytesIO()
        wf = wave.open(wav_buffer, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(audio_data)
        wf.close()
        
        # Reset buffer position to beginning
        wav_buffer.seek(0)
        
        # Send as multipart form data
        files = {'audio': ('command.wav', wav_buffer, 'audio/wav')}
        response = requests.post(API_URL, files=files, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            
            # Print what was said
            print(f"You said: {result.get('transcription', 'Nothing detected')}")
            print(f"Coach says: {result.get('message', '')}")

            # Handle audio response
            if result.get('audio_response'):
                # Convert base64 to audio file
                audio_bytes = base64.b64decode(result['audio_response'])
                response_file = '/tmp/coach_response.wav'
                
                with open(response_file, 'wb') as f:
                    f.write(audio_bytes)
                
                # Play the audio file
                print("Playing coach's audio response...")
                play_audio(response_file)
            else:
                # No audio, use text-to-speech fallback
                if result.get('message'):
                    speak_text(result['message'])
        else:
            print(f"✗ API error: {response.status_code}")
            if response.text:
                print(f"Error details: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print(f"✗ Could not connect to API at {API_URL}")
    except requests.exceptions.Timeout:
        print(f"✗ API request timed out")
    except requests.exceptions.JSONDecodeError:
        print(f"✗ Invalid JSON response from API")
        print(f"Response text: {response.text}")
    except Exception as e:
        print(f"✗ Error: {e}")

def pressed():
    global timer
    timer = threading.Timer(0.5, start_recording)
    timer.start()

def released():
    global timer, recording, frames
    if timer: 
        timer.cancel()
    
    if recording:
        recording = False
        if frames:
            audio_data = b''.join(frames)
            duration = len(frames) * 1024 / 16000
            print(f"Recording ended ({duration:.1f}s). Sending to API...")
            
            # Send to API and handle response
            send_voice_and_handle_response(audio_data)
            
            # Optionally save recording locally for debugging
            # wf = wave.open("recording.wav", 'wb')
            # wf.setnchannels(1)
            # wf.setsampwidth(2)
            # wf.setframerate(16000)
            # wf.writeframes(audio_data)
            # wf.close()
    else:
        print("Click!")

def start_recording():
    global recording
    recording = True
    print("Starting recording...")
    threading.Thread(target=record).start()

button.when_pressed = pressed
button.when_released = released

print(f"Voice control ready. API endpoint: {API_URL}")
print("Hold button 0.5s to record, release to send and hear response")
pause()