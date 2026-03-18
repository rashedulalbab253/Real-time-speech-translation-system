# 🎙️ Bengali-English Speech Translation Suite

A professional, real-time bidirectional speech translation and conversational AI assistant system designed for video calls, meetings, and personal assistance.

---

## 🚀 Overview

This suite features two production-grade applications built with **Gemini 2.0 Flash** for ultra-fast, high-accuracy language processing. Both apps feature a modern, dark-themed **CustomTkinter** UI for a premium user experience.

### 1. 📂 `speech_translator.py`
**Goal:** Bidirectional Translation (Person-to-Person)
*   Translates **English to Bengali** and **Bengali to English** simultaneously.
*   Ideal for meetings where two people speak different languages.
*   Uses smart voice-activity detection to wait for you to finish speaking before translating.

### 2. 📂 `voice_bot.py`
**Goal:** Intelligent AI Assistant (Person-to-AI)
*   Talk directly to Gemini in either English or Bengali.
*   Gemini understands context and remembers previous parts of the conversation.
*   Great for asking questions, brainstorming, or practicing a new language.

---

## ✨ Features

*   **Premium UI:** Modern dark-mode interface with real-time status indicators.
*   **Dual Language Support:** Full support for `en-US` and `bn-BD`.
*   **Smart Rate Limiting:** Built-in 60-second cooldown recovery to handle Gemini API quotas.
*   **High Accuracy:** Powered by Google's `gemini-2.0-flash` for natural-sounding translations.
*   **Multi-mode TTS:** Integrated Google TTS and System TTS for clear speaking feedback.
*   **Persistent History:** Save your conversations to `.json` files and reload them later.

---

## 🛠️ Step-by-Step Installation

### 1. Prerequisites
*   Python **3.10+**
*   Active Internet Connection
*   A Microphone 🎙️

### 2. Install Dependencies
Open your terminal in the project folder and run:
```bash
pip install -r requirements.txt
```

### 3. Get Your API Key
You need a free Google Generative AI key:
1.  Go to [Google AI Studio](https://aistudio.google.com/)
2.  Click **"Get API key"**.
3.  Copy and paste it into the app window when launched.

---

## 🚀 Quick Start

### To Run the Speech Translator:
```bash
python speech_translator.py
```
1.  Enter your API Key.
2.  Click **Initialize Translator**.
3.  Click **"Start Listening (English)"** or **"Start Listening (Bengali)"**.
4.  Speak naturally—the app will wait for you to pause, then translate and speak.

### To Run the Voice Bot:
```bash
python voice_bot.py
```
1.  Set your language toggle (English or Bengali).
2.  Click **Start Listening**.
3.  Ask the AI a question—it will reply with both text and voice!

---

## 🏗️ Tech Stack
*   **Speech Recognition:** `SpeechRecognition` (Google Web Speech API)
*   **Core AI Engine:** `google-generativeai` (Gemini 2.0 Flash)
*   **UI Framework:** `CustomTkinter` (Modern Dark Theme)
*   **Audio Engine:** `pygame`, `pyttsx3`, `gTTS`
*   **Data Handling:** `Python threading`, `JSON history`

---

## 📖 Best Practices
*   **API Quota:** The Gemini free tier is limited to 15 requests per minute. If you speak too rapidly, the app will pause for 60 seconds to reset your quota.
*   **Audio Clarity:** Speak clearly and wait for the "Listening" status to appear on the UI before starting your sentence.
*   **Microphone Setup:** Ensure your default system microphone is correctly configured in Windows.