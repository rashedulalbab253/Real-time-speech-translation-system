import speech_recognition as sr
import pyttsx3
import google.generativeai as genai
import pygame
import threading
import queue
import time
import customtkinter as ctk
import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog
import logging
import os
from datetime import datetime
import json
import re
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GeminiVoiceBot:
    def __init__(self, api_key):
        """Initialize the Gemini Voice Bot"""
        self.api_key = api_key
        self.setup_gemini()
        self.setup_speech_recognition()
        self.setup_tts()
        self.setup_audio()
        
        # Bot state
        self.is_listening = False
        self.current_language = "english"  # Default language
        self.is_running = True
        self.is_speaking = False
        
        # Conversation history
        self.conversation_history = []
        self.max_history_length = 10  # Keep last 10 exchanges for context
        
        # Language settings
        self.language_codes = {
            "english": {"speech": "en-US", "tts": "en", "display": "🇺🇸 English"},
            "bengali": {"speech": "bn-BD", "tts": "bn", "display": "🇧🇩 Bengali"}
        }
        
    def setup_gemini(self):
        """Configure Gemini AI"""
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.0-flash')
            
            # Test the connection
            test_response = self.model.generate_content("Hello, respond with just 'OK' to confirm connection.")
            logger.info(f"Gemini AI connected successfully. Test response: {test_response.text}")
        except Exception as e:
            logger.error(f"Error configuring Gemini AI: {e}")
            raise
    
    def setup_speech_recognition(self):
        """Initialize speech recognition"""
        self.recognizer = sr.Recognizer()
        
        # Optimize recognition settings
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.pause_threshold = 1.5
        self.recognizer.operation_timeout = None
        self.recognizer.phrase_threshold = 0.3
        self.recognizer.non_speaking_duration = 1.5
        
        # Get microphone
        self.microphone = sr.Microphone()
        
        # Calibrate for ambient noise
        try:
            with self.microphone as source:
                logger.info("Calibrating microphone for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=2)
            logger.info("Speech recognition initialized successfully")
        except Exception as e:
            logger.error(f"Microphone calibration failed: {e}")
    
    def setup_tts(self):
        """Initialize Text-to-Speech engines"""
        # English TTS
        self.tts_english = pyttsx3.init()
        voices_en = self.tts_english.getProperty('voices')
        
        # Set English voice (prefer female voice)
        for voice in voices_en:
            if 'english' in voice.name.lower() or 'en' in voice.id.lower():
                self.tts_english.setProperty('voice', voice.id)
                break
        
        self.tts_english.setProperty('rate', 160)
        self.tts_english.setProperty('volume', 0.9)
        
        # Bengali TTS setup
        self.use_google_tts_for_bengali = True
        try:
            self.tts_bengali = pyttsx3.init()
            voices_bn = self.tts_bengali.getProperty('voices')
            
            for voice in voices_bn:
                if any(keyword in voice.name.lower() for keyword in ['bengali', 'bn', 'bangla']):
                    self.tts_bengali.setProperty('voice', voice.id)
                    self.use_google_tts_for_bengali = False
                    break
            
            if not self.use_google_tts_for_bengali:
                self.tts_bengali.setProperty('rate', 150)
                self.tts_bengali.setProperty('volume', 0.9)
                
        except Exception as e:
            logger.warning(f"Bengali TTS setup failed: {e}")
        
        logger.info("TTS engines initialized")
    
    def setup_audio(self):
        """Initialize pygame for audio playback"""
        try:
            pygame.mixer.init()
            logger.info("Audio system initialized")
        except Exception as e:
            logger.error(f"Audio system initialization failed: {e}")
    
    def listen_for_speech(self):
        """Listen for speech input"""
        try:
            with self.microphone as source:
                # Quick ambient noise adjustment
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                
                # Listen for speech
                logger.info(f"Listening for {self.current_language}...")
                audio = self.recognizer.listen(
                    source, 
                    timeout=3,  # Wait 3 seconds for speech to start
                    phrase_time_limit=30  # Maximum 30 seconds per phrase
                )
            
            # Recognize speech
            language_code = self.language_codes[self.current_language]["speech"]
            
            if self.current_language == "bengali":
                text = self.recognizer.recognize_google(audio, language="bn-BD")
            else:
                text = self.recognizer.recognize_google(audio, language="en-US")
            
            if len(text.strip()) > 1:  # Valid speech
                logger.info(f"Recognized: {text}")
                return text
            return None
                
        except sr.WaitTimeoutError:
            logger.debug("No speech detected within timeout")
            return None
        except sr.UnknownValueError:
            logger.debug("Could not understand audio")
            return None
        except sr.RequestError as e:
            logger.error(f"Speech recognition error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in speech recognition: {e}")
            return None
    
    def get_gemini_response(self, user_input):
        """Get response from Gemini AI with conversation context"""
        try:
            # Build conversation context
            context = self.build_conversation_context()
            
            # Create enhanced prompt based on language
            if self.current_language == "bengali":
                system_prompt = """You are a helpful AI assistant that responds in Bengali. 
                Please provide natural, conversational responses in Bengali. 
                Be friendly, informative, and culturally appropriate.
                Keep responses concise but complete."""
            else:
                system_prompt = """You are a helpful AI assistant. 
                Please provide natural, conversational responses in English.
                Be friendly, informative, and helpful.
                Keep responses concise but complete."""
            
            # Combine context and current input
            full_prompt = f"{system_prompt}\n\nConversation history:\n{context}\n\nUser: {user_input}\n\nAssistant:"
            
            # Get response from Gemini
            response = self.model.generate_content(full_prompt)
            response_text = response.text.strip()
            
            # Clean up response
            response_text = self.clean_response(response_text)
            
            # Add to conversation history
            self.add_to_history(user_input, response_text)
            
            logger.info(f"Gemini response: {response_text}")
            return response_text
            
        except Exception as e:
            logger.error(f"Error getting Gemini response: {e}")
            error_msg = "Sorry, I encountered an error. Please try again."
            if self.current_language == "bengali":
                error_msg = "দুঃখিত, একটি ত্রুটি হয়েছে। অনুগ্রহ করে আবার চেষ্টা করুন।"
            return error_msg
    
    def build_conversation_context(self):
        """Build conversation context from recent history"""
        if not self.conversation_history:
            return "No previous conversation."
        
        context_lines = []
        for exchange in self.conversation_history[-5:]:  # Last 5 exchanges
            context_lines.append(f"User: {exchange['user']}")
            context_lines.append(f"Assistant: {exchange['assistant']}")
        
        return "\n".join(context_lines)
    
    def clean_response(self, response_text):
        """Clean up the AI response"""
        # Remove any unwanted prefixes or artifacts
        response_text = re.sub(r'^(Assistant:|AI:|Bot:)\s*', '', response_text, flags=re.IGNORECASE)
        response_text = response_text.strip()
        
        # Limit response length for better speech output
        if len(response_text) > 500:
            sentences = response_text.split('.')
            response_text = '. '.join(sentences[:3]) + '.'
        
        return response_text
    
    def add_to_history(self, user_input, assistant_response):
        """Add exchange to conversation history"""
        self.conversation_history.append({
            'timestamp': datetime.now().isoformat(),
            'user': user_input,
            'assistant': assistant_response,
            'language': self.current_language
        })
        
        # Keep only recent history
        if len(self.conversation_history) > self.max_history_length:
            self.conversation_history = self.conversation_history[-self.max_history_length:]
    
    def speak_text(self, text):
        """Convert text to speech"""
        if self.is_speaking:  # Prevent overlapping speech
            return
            
        self.is_speaking = True
        try:
            if self.current_language == "english":
                self.speak_english(text)
            else:
                self.speak_bengali(text)
        except Exception as e:
            logger.error(f"TTS error: {e}")
        finally:
            self.is_speaking = False
    
    def speak_english(self, text):
        """Speak text in English"""
        try:
            self.tts_english.say(text)
            self.tts_english.runAndWait()
        except Exception as e:
            logger.error(f"English TTS error: {e}")
    
    def speak_bengali(self, text):
        """Speak text in Bengali"""
        try:
            if self.use_google_tts_for_bengali:
                self.speak_with_google_tts(text)
            else:
                self.tts_bengali.say(text)
                self.tts_bengali.runAndWait()
        except Exception as e:
            logger.error(f"Bengali TTS error: {e}")
            # Fallback to Google TTS
            try:
                self.speak_with_google_tts(text)
            except:
                logger.error("All Bengali TTS methods failed")
    
    def speak_with_google_tts(self, text):
        """Use Google TTS for Bengali speech"""
        try:
            from gtts import gTTS
            import tempfile
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as tmp_file:
                temp_filename = tmp_file.name
            
            # Generate speech
            tts = gTTS(text=text, lang='bn', slow=False)
            tts.save(temp_filename)
            
            # Play audio
            pygame.mixer.music.load(temp_filename)
            pygame.mixer.music.play()
            
            # Wait for completion
            while pygame.mixer.music.get_busy():
                pygame.time.wait(100)
            
            # Cleanup
            try:
                os.unlink(temp_filename)
            except:
                pass
                
        except ImportError:
            logger.error("gTTS not installed. Install with: pip install gtts")
        except Exception as e:
            logger.error(f"Google TTS error: {e}")
    
    def process_voice_interaction(self):
        """Main voice interaction loop"""
        while self.is_running and self.is_listening:
            try:
                # Update GUI status
                if hasattr(self, 'update_status_callback'):
                    lang_display = self.language_codes[self.current_language]["display"]
                    self.update_status_callback(f"🎤 Listening for {lang_display}...")
                
                # Listen for speech
                user_input = self.listen_for_speech()
                
                if user_input:
                    # Update GUI with user input
                    if hasattr(self, 'update_conversation_callback'):
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        self.update_conversation_callback(f"[{timestamp}] You: {user_input}\n")
                    
                    # Update status
                    if hasattr(self, 'update_status_callback'):
                        self.update_status_callback("🤖 Thinking...")
                    
                    # Get AI response
                    ai_response = self.get_gemini_response(user_input)
                    
                    # Update GUI with AI response
                    if hasattr(self, 'update_conversation_callback'):
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        self.update_conversation_callback(f"[{timestamp}] Bot: {ai_response}\n\n")
                    
                    # Update status
                    if hasattr(self, 'update_status_callback'):
                        self.update_status_callback("🔊 Speaking...")
                    
                    # Speak response
                    self.speak_text(ai_response)
                    
                    # Reset status
                    if hasattr(self, 'update_status_callback'):
                        lang_display = self.language_codes[self.current_language]["display"]
                        self.update_status_callback(f"✅ Ready for {lang_display}")
                
                # Brief pause to prevent CPU spike
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error in voice interaction: {e}")
                time.sleep(1)  # Brief pause before retrying
    
    def start_listening(self):
        """Start voice interaction"""
        self.is_listening = True
        logger.info("Started voice interaction")
    
    def stop_listening(self):
        """Stop voice interaction"""
        self.is_listening = False
        logger.info("Stopped voice interaction")
    
    def set_language(self, language):
        """Set the current language"""
        if language in self.language_codes:
            self.current_language = language
            logger.info(f"Language set to: {language}")
    
    def save_conversation(self, filename=None):
        """Save conversation history"""
        try:
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"voice_bot_conversation_{timestamp}.json"
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.conversation_history, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Conversation saved to {filename}")
            return filename
        except Exception as e:
            logger.error(f"Error saving conversation: {e}")
            return None
    
    def load_conversation(self, filename):
        """Load conversation history"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                self.conversation_history = json.load(f)
            logger.info(f"Conversation loaded from {filename}")
            return True
        except Exception as e:
            logger.error(f"Error loading conversation: {e}")
            return False
    
    def clear_conversation(self):
        """Clear conversation history"""
        self.conversation_history.clear()
        logger.info("Conversation history cleared")
    
    def stop(self):
        """Stop the voice bot"""
        self.is_running = False
        self.is_listening = False
        logger.info("Voice bot stopped")


class VoiceBotGUI:
    def __init__(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        self.root = ctk.CTk()
        self.root.title("🤖 Gemini Voice Bot - English & Bengali")
        self.root.geometry("1000x800")
        
        self.voice_bot = None
        self.bot_thread = None
        self.setup_gui()
    
    def setup_gui(self):
        """Setup the GUI interface"""
        # Main title
        title_label = ctk.CTkLabel(self.root, text="🤖 Gemini Voice Bot", 
                                  font=ctk.CTkFont(size=32, weight="bold"))
        title_label.pack(pady=(25, 5))
        
        subtitle_label = ctk.CTkLabel(self.root, text="Intelligent Assistant with English & Bengali Support", 
                                     font=ctk.CTkFont(size=14), text_color="#94a3b8")
        subtitle_label.pack(pady=(0, 20))
        
        # Main container with two columns
        main_container = ctk.CTkFrame(self.root, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=30, pady=10)
        
        # Left Panel: Configuration & Controls (35% width)
        left_panel = ctk.CTkFrame(main_container, width=320)
        left_panel.pack(side="left", fill="both", padx=(0, 15))
        left_panel.pack_propagate(False)
        
        # Config Section
        ctk.CTkLabel(left_panel, text="Settings", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(20, 15))
        
        ctk.CTkLabel(left_panel, text="Gemini API Key:", font=ctk.CTkFont(size=13)).pack(anchor="w", padx=20)
        self.api_key_entry = ctk.CTkEntry(left_panel, show="*", placeholder_text="Enter API Key...")
        self.api_key_entry.pack(fill="x", padx=20, pady=(5, 15))
        
        self.init_btn = ctk.CTkButton(left_panel, text="Initialize Bot", 
                                     command=self.initialize_bot,
                                     fg_color="#3498db", hover_color="#2980b9", font=ctk.CTkFont(weight="bold"))
        self.init_btn.pack(pady=10, padx=20, fill="x")
        
        # Divider
        ctk.CTkFrame(left_panel, height=2, fg_color="#334155").pack(fill="x", padx=20, pady=20)
        
        # Controls Section
        ctk.CTkLabel(left_panel, text="Controls", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(0, 15))
        
        ctk.CTkLabel(left_panel, text="Select Language:", font=ctk.CTkFont(size=13)).pack(anchor="w", padx=20)
        self.language_var = tk.StringVar(value="english")
        
        lang_switch_frame = ctk.CTkFrame(left_panel, fg_color="transparent")
        lang_switch_frame.pack(pady=10, padx=20, fill="x")
        
        self.english_radio = ctk.CTkRadioButton(lang_switch_frame, text="🇺🇸 English", 
                                               variable=self.language_var, value="english",
                                               command=self.change_language, state='disabled')
        self.english_radio.pack(side="left", padx=10)
        
        self.bengali_radio = ctk.CTkRadioButton(lang_switch_frame, text="🇧🇩 Bengali", 
                                               variable=self.language_var, value="bengali",
                                               command=self.change_language, state='disabled')
        self.bengali_radio.pack(side="left", padx=10)
        
        self.listen_btn = ctk.CTkButton(left_panel, text="Start Listening", 
                                       command=self.toggle_listening,
                                       fg_color="#27ae60", hover_color="#219653", 
                                       state='disabled', font=ctk.CTkFont(weight="bold"), height=45)
        self.listen_btn.pack(pady=15, padx=20, fill="x")
        
        self.stop_btn = ctk.CTkButton(left_panel, text="Stop Bot", 
                                     command=self.stop_bot,
                                     fg_color="#e74c3c", hover_color="#c0392b", 
                                     state='disabled', height=40)
        self.stop_btn.pack(pady=5, padx=20, fill="x")
        
        # Status Section at bottom of left panel
        status_frame = ctk.CTkFrame(left_panel, fg_color="#1e293b", corner_radius=10)
        status_frame.pack(side="bottom", fill="x", padx=15, pady=20)
        
        self.status_label = ctk.CTkLabel(status_frame, text="Status: Not initialized", 
                                        text_color="#94a3b8", font=ctk.CTkFont(size=12))
        self.status_label.pack(pady=10)
        
        # Right Panel: Conversation (65% width)
        right_panel = ctk.CTkFrame(main_container)
        right_panel.pack(side="right", fill="both", expand=True)
        
        # Conversation text area
        self.conversation_display = ctk.CTkTextbox(right_panel, font=ctk.CTkFont("Consolas", size=14),
                                                  fg_color="#0f172a", text_color="#f8fafc", spacing3=8)
        self.conversation_display.pack(fill="both", expand=True, padx=15, pady=15)
        
        # File operations frame
        file_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        file_frame.pack(fill="x", side="bottom", padx=15, pady=(0, 15))
        
        self.save_btn = ctk.CTkButton(file_frame, text="Save Chat", 
                                     command=self.save_conversation, state='disabled',
                                     fg_color="#9b59b6", hover_color="#8e44ad", width=100)
        self.save_btn.pack(side="left", padx=5)
        
        self.load_btn = ctk.CTkButton(file_frame, text="Load History", 
                                     command=self.load_conversation, state='disabled',
                                     fg_color="#f39c12", hover_color="#d35400", width=100)
        self.load_btn.pack(side="left", padx=5)
        
        self.clear_btn = ctk.CTkButton(file_frame, text="Clear chat", 
                                      command=self.clear_display, state='disabled',
                                      fg_color="#475569", hover_color="#334155", width=100)
        self.clear_btn.pack(side="right", padx=5)
    
    def initialize_bot(self):
        """Initialize the voice bot"""
        api_key = self.api_key_entry.get().strip()
        if not api_key:
            messagebox.showerror("Error", "Please enter your Gemini API key")
            return
        
        try:
            self.init_btn.configure(text="Initializing...", state='disabled')
            self.root.update()
            
            self.voice_bot = GeminiVoiceBot(api_key)
            self.voice_bot.update_conversation_callback = self.update_conversation_display
            self.voice_bot.update_status_callback = self.update_status
            
            # Enable controls
            self.listen_btn.configure(state='normal')
            self.stop_btn.configure(state='normal')
            self.save_btn.configure(state='normal')
            self.load_btn.configure(state='normal')
            self.clear_btn.configure(state='normal')
            self.english_radio.configure(state='normal')
            self.bengali_radio.configure(state='normal')
            
            self.init_btn.configure(text="Bot Initialized", fg_color="#27ae60")
            self.status_label.configure(text="Status: Ready to talk! 🤖", text_color="#2ecc71")
            
            messagebox.showinfo("Success", "Voice Bot initialized successfully!")
            
        except Exception as e:
            self.init_btn.configure(text="Initialize Bot", state='normal', fg_color="#3498db")
            messagebox.showerror("Error", f"Failed to initialize voice bot: {str(e)}")
    
    def toggle_listening(self):
        """Toggle listening state"""
        if not self.voice_bot:
            return
        
        if not self.voice_bot.is_listening:
            self.voice_bot.start_listening()
            self.listen_btn.configure(text="Stop Listening", fg_color="#e74c3c", hover_color="#c0392b")
            self.bot_thread = threading.Thread(target=self.voice_bot.process_voice_interaction, daemon=True)
            self.bot_thread.start()
        else:
            self.voice_bot.stop_listening()
            self.listen_btn.configure(text="Start Listening", fg_color="#27ae60", hover_color="#219653")
    
    def stop_bot(self):
        """Stop the voice bot completely"""
        if self.voice_bot:
            self.voice_bot.stop()
            self.listen_btn.configure(text="Start Listening", fg_color="#27ae60", hover_color="#219653")
            self.status_label.configure(text="Status: Stopped ⏸️", text_color="#94a3b8")
    
    def change_language(self):
        """Change the bot language"""
        if self.voice_bot:
            language = self.language_var.get()
            self.voice_bot.set_language(language)
            lang_display = self.voice_bot.language_codes[language]["display"]
            self.update_status(f"Ready for {lang_display} 🌐")
    
    def update_status(self, status_text):
        """Update the status label"""
        if hasattr(self, 'status_label'):
            self.status_label.configure(text=f"Status: {status_text}", text_color="#3498db")
    
    def update_conversation_display(self, text):
        """Update the conversation display"""
        self.conversation_display.insert("end", text)
        self.conversation_display.see("end")
        self.root.update_idletasks()
    
    def save_conversation(self):
        """Save conversation to file"""
        if not self.voice_bot or not self.voice_bot.conversation_history:
            messagebox.showinfo("Info", "No conversation to save")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Save Conversation"
        )
        
        if filename:
            saved_file = self.voice_bot.save_conversation(filename)
            if saved_file:
                messagebox.showinfo("Success", f"Conversation saved to file.")
    
    def load_conversation(self):
        """Load conversation from file"""
        if not self.voice_bot:
            return
        
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Load Conversation"
        )
        
        if filename and self.voice_bot.load_conversation(filename):
            self.clear_display()
            for exchange in self.voice_bot.conversation_history:
                timestamp = exchange.get('timestamp', 'Unknown')[11:19]
                user_msg = exchange.get('user', '')
                bot_msg = exchange.get('assistant', '')
                lang = exchange.get('language', 'unknown')
                self.update_conversation_display(f"[{timestamp}] YOU ({lang}): {user_msg}\n")
                self.update_conversation_display(f"[{timestamp}] BOT: {bot_msg}\n\n")
            messagebox.showinfo("Success", f"Conversation loaded.")
    
    def clear_display(self):
        """Clear the conversation display"""
        self.conversation_display.delete('1.0', "end")
        if self.voice_bot:
            self.voice_bot.clear_conversation()
    
    def on_closing(self):
        """Handle window closing"""
        if self.voice_bot:
            self.voice_bot.stop()
        self.root.destroy()
    
    def run(self):
        """Run the GUI application"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()           self.voice_bot.stop()
        self.root.destroy()
    
    def run(self):
        """Run the GUI application"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()


def main():
    """Main function to run the application"""
    try:
        # Check required dependencies
        required_modules = ['speech_recognition', 'pyttsx3', 'google.generativeai', 'pygame']
        missing_modules = []
        
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                missing_modules.append(module)
        
        if missing_modules:
            print("❌ Missing required modules:")
            for module in missing_modules:
                print(f"   - {module}")
            print("\n📥 Install missing modules with:")
            print("pip install speech_recognition pyttsx3 google-generativeai pygame gtts")
            return
        
        # Run the application
        app = VoiceBotGUI()
        app.run()
        
    except Exception as e:
        logger.error(f"Application error: {e}")
        print(f"❌ Error starting application: {e}")


if __name__ == "__main__":
    main()