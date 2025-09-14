"""
Voice Chess Coach with Groq TTS
Uses Calum voice (calm and patient) for a friendly coaching experience
"""

import os
import io
import sys
import time
import tempfile
import subprocess
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from groq import Groq

# Import our chess coach
from chess_coach_ai import process_user_input

# Load environment variables
# Try both paths - from backend directory and from root
if os.path.exists('../config.env'):
    load_dotenv('../config.env')
else:
    load_dotenv('config.env')

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_TTS_API_KEY = os.getenv("GROQ_TTS_API_KEY")  # Separate TTS key

if not GROQ_API_KEY:
    # Try to help debug
    current_dir = os.getcwd()
    config_exists = os.path.exists('../config.env') or os.path.exists('config.env')
    raise ValueError(f"GROQ_API_KEY not found. Current dir: {current_dir}, config.env exists: {config_exists}")

# Use main key for chat/transcription
groq_client = Groq(api_key=GROQ_API_KEY)

# Create separate client for TTS if we have a TTS-specific key
groq_tts_client = Groq(api_key=GROQ_TTS_API_KEY) if GROQ_TTS_API_KEY else groq_client

print("🎙️ Voice Chess Coach initialized")

class VoiceCoach:
    def __init__(self):
        # Use Calum voice - calm and patient, perfect for coaching
        self.voice = "Calum-PlayAI"
        self.tts_model = "playai-tts"
        print(f"🎭 Using {self.voice} (calm and patient voice)")
        
    def record_audio(self, duration: int = 5) -> Optional[str]:
        """Record audio from microphone"""
        temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        temp_file.close()
        
        print(f"🎤 Recording for {duration} seconds... Speak now!")
        
        if sys.platform == 'darwin':  # macOS
            try:
                # Try sox first (better quality)
                cmd = ['rec', '-q', temp_file.name, 'trim', '0', str(duration)]
                subprocess.run(cmd, check=True, capture_output=True)
            except FileNotFoundError:
                # Fallback to macOS built-in
                cmd = ['afrecord', '-d', str(duration), '-f', 'WAVE', '-r', '16000', temp_file.name]
                try:
                    subprocess.run(cmd, check=True, capture_output=True)
                except:
                    print("❌ Recording failed. Install sox: brew install sox")
                    return None
        else:
            print("⚠️  Recording not configured for this platform")
            return None
            
        print("✅ Recording complete")
        return temp_file.name
    
    def transcribe_audio(self, audio_file_path: str) -> Optional[str]:
        """Transcribe audio using Groq Whisper"""
        try:
            with open(audio_file_path, "rb") as audio_file:
                print("📤 Transcribing...")
                
                transcription = groq_client.audio.transcriptions.create(
                    file=audio_file,
                    model="whisper-large-v3-turbo",
                    language="en",
                    temperature=0.0,
                    response_format="text",
                    prompt="Chess moves: e2 e4, knight f3, analyze, hint, castle"
                )
                
                os.unlink(audio_file_path)
                return transcription.strip()
                
        except Exception as e:
            print(f"❌ Transcription error: {e}")
            if os.path.exists(audio_file_path):
                os.unlink(audio_file_path)
            return None
    
    def speak(self, text: str):
        """Convert text to speech using Groq TTS with Calum voice"""
        # Clean text for speech
        clean_text = text.replace('*', '').replace('_', '').replace('#', '').replace('`', '')
        
        # Limit length
        if len(clean_text) > 500:
            clean_text = clean_text[:497] + "..."
        
        try:
            # Generate speech with Groq
            response = groq_tts_client.audio.speech.create(  # Use TTS-specific client
                model=self.tts_model,
                voice=self.voice,
                input=clean_text,
                response_format="wav"
            )
            
            # Save and play
            temp_audio = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            response.write_to_file(temp_audio.name)
            
            # Play audio
            if sys.platform == 'darwin':
                subprocess.run(['afplay', temp_audio.name], check=False)
            elif sys.platform == 'linux':
                subprocess.run(['aplay', temp_audio.name], check=False)
            
            # Clean up
            os.unlink(temp_audio.name)
            
        except Exception as e:
            print(f"⚠️  TTS failed: {e}")
            # Fallback
            if sys.platform == 'darwin':
                subprocess.run(['say', '-r', '150', clean_text], check=False)
            else:
                print(f"🔊 {clean_text}")
    
    def enhance_command(self, raw_text: str) -> str:
        """Clean up speech-to-text for chess commands"""
        if not raw_text:
            return raw_text
            
        text_lower = raw_text.lower()
        
        # Already clear?
        if any(word in text_lower for word in ['move', 'analyze', 'hint', 'castle', 'fork']):
            return raw_text
        
        # Use LLM to fix unclear speech
        try:
            prompt = f'Convert to chess command: "{raw_text}"\nReturn ONLY the command like "Move e2 to e4"'
            
            completion = groq_client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": "Convert speech to chess commands."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=30
            )
            
            enhanced = completion.choices[0].message.content.strip()
            if enhanced:
                return enhanced
            return raw_text
        except Exception as e:
            print(f"Enhancement failed: {e}")
            return raw_text
    
    def process_voice(self, duration: int = 5) -> Dict[str, Any]:
        """Complete voice interaction cycle"""
        
        # Clear indication that we're listening
        print("\n" + "="*50)
        print("🔴 LISTENING NOW - SPEAK YOUR COMMAND!")
        print("="*50)
        
        # Record
        audio_file = self.record_audio(duration)
        if not audio_file:
            self.speak("Recording failed. Please try again.")
            return {"success": False}
        
        # Transcribe
        transcription = self.transcribe_audio(audio_file)
        if not transcription:
            self.speak("I didn't catch that. Please try again.")
            return {"success": False}
        
        print(f"🗣️ You said: \"{transcription}\"")
        
        # Enhance if needed
        command = self.enhance_command(transcription)
        if command != transcription:
            print(f"🔧 Enhanced to: \"{command}\"")
        
        # Process command
        result = process_user_input(command)
        
        # Speak response with better feedback
        if result.get("message"):
            # Make response more natural
            message = result['message']
            if not message or len(message) < 3:
                # Empty or too short response, provide better feedback
                message = "I processed your command. What would you like to do next?"
            
            print(f"🤖 Coach: {message}")
            self.speak(message)
        else:
            # No message returned, provide feedback
            self.speak("Command processed. Ready for your next move.")
        
        return result

def main():
    """Main entry point"""
    
    print("\n" + "="*60)
    print("🎙️  VOICE CHESS COACH")
    print("    Using Calum voice (calm and patient)")
    print("="*60)
    
    print("\n⚠️  Make sure backend is running:")
    print("   cd backend && uvicorn main:app --reload")
    
    coach = VoiceCoach()
    
    # Welcome
    coach.speak("Welcome to Chess Coach. I'm here to help you improve your game.")
    
    print("\n📌 COMMANDS:")
    print("  • ENTER = Record 5 seconds")
    print("  • Number = Record N seconds")
    print("  • 'text' = Type command")
    print("  • 'quit' = Exit")
    
    print("\n💡 VOICE EXAMPLES:")
    print("  • 'Move e2 to e4'")
    print("  • 'Give me a hint'")
    print("  • 'Analyze the position'")
    print("  • 'What is castling?'")
    print("="*60)
    
    while True:
        print("\n" + "-"*40)
        user_input = input("Press ENTER to speak (or 'quit'): ").strip().lower()
        
        if user_input in ['quit', 'exit', 'q']:
            coach.speak("Goodbye! Keep practicing!")
            break
        
        elif user_input == 'text':
            text_input = input("Type command: ").strip()
            if text_input:
                result = process_user_input(text_input)
                if result.get("message"):
                    print(f"🤖 Coach: {result['message']}")
                    coach.speak(result['message'])
        
        elif user_input.isdigit():
            # Custom duration
            duration = min(int(user_input), 15)
            coach.process_voice(duration)
        
        else:
            # Default 5 seconds
            try:
                coach.process_voice(5)
            except KeyboardInterrupt:
                print("\n⏹️  Cancelled")
            except Exception as e:
                print(f"❌ Error: {e}")
                coach.speak("Something went wrong. Try again.")

if __name__ == "__main__":
    main()
