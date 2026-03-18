import speech_recognition as sr
import pyttsx3
import google.generativeai as genai
import pygame
import threading
import queue
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
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
        self.root = tk.Tk()
        self.root.title("🤖 Gemini Voice Bot - English & Bengali")
        self.root.geometry("1000x750")
        self.root.configure(bg='#f8f9fa')
        
        # Apply modern styling
        self.setup_styles()
        
        self.voice_bot = None
        self.bot_thread = None
        self.setup_gui()
    
    def setup_styles(self):
        """Setup modern styling"""
        try:
            self.style = ttk.Style()
            self.style.theme_use('clam')
            
            # Configure custom styles
            self.style.configure('Title.TLabel', font=('Arial', 16, 'bold'))
            self.style.configure('Heading.TLabel', font=('Arial', 12, 'bold'))
            self.style.configure('Custom.TButton', font=('Arial', 10, 'bold'))
        except Exception as e:
            logger.warning(f"Could not setup custom styles: {e}")
            # Use basic styling as fallback
            self.style = ttk.Style()
    
    def setup_gui(self):
        """Setup the GUI interface"""
        # Main title
        title_frame = tk.Frame(self.root, bg='#f8f9fa')
        title_frame.pack(fill="x", pady=10)
        
        title_label = tk.Label(title_frame, text="🤖 Gemini Voice Bot", 
                              font=("Arial", 24, "bold"), bg='#f8f9fa', fg='#2c3e50')
        title_label.pack()
        
        subtitle_label = tk.Label(title_frame, text="Intelligent Voice Assistant with English & Bengali Support", 
                                 font=("Arial", 12), bg='#f8f9fa', fg='#7f8c8d')
        subtitle_label.pack()
        
        # Configuration Frame
        config_frame = ttk.LabelFrame(self.root, text="🔧 Configuration", padding=15)
        config_frame.pack(fill="x", padx=20, pady=10)
        
        # API Key input
        tk.Label(config_frame, text="Gemini API Key:", font=("Arial", 11, "bold")).pack(anchor="w")
        self.api_key_entry = tk.Entry(config_frame, width=70, show="*", font=("Arial", 10))
        self.api_key_entry.pack(fill="x", pady=(5, 10))
        
        # Initialize button
        self.init_btn = tk.Button(config_frame, text="🚀 Initialize Voice Bot", 
                                 command=self.initialize_bot,
                                 bg='#3498db', fg='white', font=("Arial", 11, "bold"),
                                 cursor='hand2', padx=15, pady=5)
        self.init_btn.pack()
        
        # Control Frame
        control_frame = ttk.LabelFrame(self.root, text="🎛️ Controls", padding=15)
        control_frame.pack(fill="x", padx=20, pady=10)
        
        # Language selection
        lang_frame = tk.Frame(control_frame)
        lang_frame.pack(fill="x", pady=(0, 10))
        
        tk.Label(lang_frame, text="🌐 Language:", font=("Arial", 11, "bold")).pack(side="left")
        
        self.language_var = tk.StringVar(value="english")
        self.english_radio = tk.Radiobutton(lang_frame, text="🇺🇸 English", 
                                           variable=self.language_var, value="english",
                                           command=self.change_language, state='disabled',
                                           font=("Arial", 10))
        self.english_radio.pack(side="left", padx=10)
        
        self.bengali_radio = tk.Radiobutton(lang_frame, text="🇧🇩 Bengali", 
                                           variable=self.language_var, value="bengali",
                                           command=self.change_language, state='disabled',
                                           font=("Arial", 10))
        self.bengali_radio.pack(side="left", padx=10)
        
        # Main control buttons
        button_frame = tk.Frame(control_frame)
        button_frame.pack(fill="x", pady=10)
        
        self.listen_btn = tk.Button(button_frame, text="🎤 Start Listening", 
                                   command=self.toggle_listening,
                                   bg='#27ae60', fg='white', font=("Arial", 12, "bold"),
                                   state='disabled', cursor='hand2', 
                                   padx=10, pady=5)
        self.listen_btn.pack(side="left", padx=5)
        
        self.stop_btn = tk.Button(button_frame, text="⏹️ Stop", 
                                 command=self.stop_bot,
                                 bg='#e74c3c', fg='white', font=("Arial", 12, "bold"),
                                 state='disabled', cursor='hand2',
                                 padx=10, pady=5)
        self.stop_btn.pack(side="left", padx=5)
        
        # Status display
        self.status_label = tk.Label(control_frame, text="Status: Not initialized ⏸️", 
                                    font=("Arial", 11), fg='#e74c3c')
        self.status_label.pack(pady=5)
        
        # Conversation Display
        conv_frame = ttk.LabelFrame(self.root, text="💬 Conversation", padding=15)
        conv_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Conversation text area
        self.conversation_display = scrolledtext.ScrolledText(
            conv_frame, height=15, font=("Consolas", 11), 
            bg='#ffffff', fg='#2c3e50', wrap=tk.WORD
        )
        self.conversation_display.pack(fill="both", expand=True, pady=(0, 10))
        
        # File operations frame
        file_frame = tk.Frame(conv_frame)
        file_frame.pack(fill="x")
        
        self.save_btn = tk.Button(file_frame, text="💾 Save Conversation", 
                                 command=self.save_conversation, state='disabled',
                                 bg='#9b59b6', fg='white', font=("Arial", 10, "bold"),
                                 cursor='hand2', padx=10, pady=3)
        self.save_btn.pack(side="left", padx=5)
        
        self.load_btn = tk.Button(file_frame, text="📂 Load Conversation", 
                                 command=self.load_conversation, state='disabled',
                                 bg='#f39c12', fg='white', font=("Arial", 10, "bold"),
                                 cursor='hand2', padx=10, pady=3)
        self.load_btn.pack(side="left", padx=5)
        
        self.clear_btn = tk.Button(file_frame, text="🗑️ Clear Display", 
                                  command=self.clear_display, state='disabled',
                                  bg='#95a5a6', fg='white', font=("Arial", 10, "bold"),
                                  cursor='hand2', padx=10, pady=3)
        self.clear_btn.pack(side="left", padx=5)
        
        # Instructions
        instructions_frame = tk.Frame(self.root, bg='#ecf0f1')
        instructions_frame.pack(fill="x", padx=20, pady=(0, 10))
        
        instructions_text = """
📖 Instructions:
1. Enter your Gemini API key and click 'Initialize Voice Bot'
2. Select your preferred language (English or Bengali)
3. Click 'Start Listening' and speak your question clearly
4. The bot will respond with voice and text
5. You can save/load conversations and switch languages anytime
        """
        
        tk.Label(instructions_frame, text=instructions_text, justify="left", 
                font=("Arial", 10), bg='#ecf0f1', fg='#2c3e50').pack(pady=10)
    
    def initialize_bot(self):
        """Initialize the voice bot"""
        api_key = self.api_key_entry.get().strip()
        if not api_key:
            messagebox.showerror("❌ Error", "Please enter your Gemini API key")
            return
        
        try:
            # Show loading
            self.init_btn.config(text="🔄 Initializing...", state='disabled')
            self.root.update()
            
            # Initialize bot
            self.voice_bot = GeminiVoiceBot(api_key)
            self.voice_bot.update_conversation_callback = self.update_conversation_display
            self.voice_bot.update_status_callback = self.update_status
            
            # Enable controls
            self.listen_btn.config(state='normal')
            self.stop_btn.config(state='normal')
            self.save_btn.config(state='normal')
            self.load_btn.config(state='normal')
            self.clear_btn.config(state='normal')
            self.english_radio.config(state='normal')
            self.bengali_radio.config(state='normal')
            
            self.init_btn.config(text="✅ Initialized", bg='#27ae60')
            self.status_label.config(text="Status: Ready to chat! 🤖", fg='#27ae60')
            
            messagebox.showinfo("✅ Success", "Voice bot initialized successfully!\nYou can now start chatting.")
            
        except Exception as e:
            self.init_btn.config(text="🚀 Initialize Voice Bot", state='normal', bg='#3498db')
            messagebox.showerror("❌ Error", f"Failed to initialize voice bot:\n{str(e)}")
    
    def toggle_listening(self):
        """Toggle listening state"""
        if not self.voice_bot:
            return
        
        if not self.voice_bot.is_listening:
            # Start listening
            self.voice_bot.start_listening()
            self.listen_btn.config(text="⏸️ Stop Listening", bg='#e74c3c')
            
            # Start bot thread
            self.bot_thread = threading.Thread(target=self.voice_bot.process_voice_interaction, daemon=True)
            self.bot_thread.start()
            
        else:
            # Stop listening
            self.voice_bot.stop_listening()
            self.listen_btn.config(text="🎤 Start Listening", bg='#27ae60')
    
    def stop_bot(self):
        """Stop the voice bot completely"""
        if self.voice_bot:
            self.voice_bot.stop()
            self.listen_btn.config(text="🎤 Start Listening", bg='#27ae60')
            self.status_label.config(text="Status: Stopped ⏹️", fg='#e74c3c')
    
    def change_language(self):
        """Change the bot language"""
        if self.voice_bot:
            language = self.language_var.get()
            self.voice_bot.set_language(language)
            lang_display = self.voice_bot.language_codes[language]["display"]
            self.status_label.config(text=f"Status: Language changed to {lang_display} 🌐", fg='#3498db')
    
    def update_status(self, status_text):
        """Update the status label"""
        if hasattr(self, 'status_label'):
            self.status_label.config(text=f"Status: {status_text}", fg='#2980b9')
    
    def update_conversation_display(self, text):
        """Update the conversation display"""
        self.conversation_display.insert(tk.END, text)
        self.conversation_display.see(tk.END)
        self.root.update_idletasks()
    
    def save_conversation(self):
        """Save conversation to file"""
        if not self.voice_bot or not self.voice_bot.conversation_history:
            messagebox.showinfo("ℹ️ Info", "No conversation to save")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Save Conversation"
        )
        
        if filename:
            saved_file = self.voice_bot.save_conversation(filename)
            if saved_file:
                messagebox.showinfo("✅ Success", f"Conversation saved to:\n{saved_file}")
    
    def load_conversation(self):
        """Load conversation from file"""
        if not self.voice_bot:
            return
        
        filename = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Load Conversation"
        )
        
        if filename and self.voice_bot.load_conversation(filename):
            # Display loaded conversation
            self.clear_display()
            for exchange in self.voice_bot.conversation_history:
                timestamp = exchange.get('timestamp', 'Unknown')[:19]  # Format timestamp
                user_msg = exchange.get('user', '')
                bot_msg = exchange.get('assistant', '')
                language = exchange.get('language', 'unknown')
                
                self.update_conversation_display(f"[{timestamp}] [{language.title()}] You: {user_msg}\n")
                self.update_conversation_display(f"[{timestamp}] [{language.title()}] Bot: {bot_msg}\n\n")
            
            messagebox.showinfo("✅ Success", f"Conversation loaded from:\n{filename}")
    
    def clear_display(self):
        """Clear the conversation display"""
        self.conversation_display.delete(1.0, tk.END)
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