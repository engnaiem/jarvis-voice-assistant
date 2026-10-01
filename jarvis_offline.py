"""
================================================================================
PROJECT: J.A.R.V.I.S. (Just A Rather Very Intelligent System)
EDITION: Continuous Conversation & English-Only Voice Daemon
AUTHOR: Mohamed Naeem
DESCRIPTION: 
    An advanced local AI assistant running as a background service. It listens 
    discreetly for a wake word ("Jarvis"), maintains an active conversation loop 
    without needing repeated wake words, processes spoken commands, executes local 
    system actions via Ollama (Qwen2.5:14b), and responds strictly in English using 
    Microsoft Edge TTS with silent background playback.
================================================================================
"""

import os
import sys

# Environment optimizations for local LLM performance
os.environ["OLLAMA_NUM_PARALLEL"] = "1"
os.environ["OLLAMA_FLASH_ATTENTION"] = "1"

import subprocess
import webbrowser
import urllib.parse
from datetime import datetime
import json
import time
import asyncio

import ollama
import chromadb
from sentence_transformers import SentenceTransformer
import edge_tts
from playsound import playsound

# Configuration constants
MODEL = "qwen2.5:14b"
VISION_MODEL = "llava"
KNOWLEDGE_DIR = "knowledge_base"
MEMORY_FILE = "jarvis_memory.json"
LONG_TERM_MEMORY_FILE = "jarvis_long_term_memory.json"

SYSTEM_PROMPT = (
    "You are JARVIS, an elite personal AI assistant running locally in the background of a Windows PC. "
    "Be polite, calm, and very concise, because your replies are read aloud. "
    "CRITICAL RULE: You MUST speak and respond strictly in ENGLISH at all times, regardless of the input language. "
    "You have powerful tools to open/close applications, play videos on YouTube, perform visual Google searches, "
    "get the current time, search local documents/PDFs, control system volume, take and analyze screenshots (vision), and manage long-term memory."
)

# ==============================================================================
# MEMORY MANAGEMENT MODULE
# ==============================================================================

def load_memory() -> list:
    """Load short-term chat history from local JSON file."""
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return [{"role": "system", "content": SYSTEM_PROMPT}]

def save_memory(memories: list) -> None:
    """Persist short-term chat history, keeping the last 20 turns."""
    clean_mems = memories[-20:]
    try:
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(clean_mems, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

messages = load_memory()

def save_to_long_term_memory(key: str, value: str) -> str:
    """Save persistent facts or details into long-term memory storage."""
    data = {}
    if os.path.exists(LONG_TERM_MEMORY_FILE):
        try:
            with open(LONG_TERM_MEMORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    data[key] = value
    with open(LONG_TERM_MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return f"Successfully remembered that {key} is {value}."

def read_long_term_memory(key: str) -> str:
    """Retrieve specific facts from long-term memory storage."""
    if not os.path.exists(LONG_TERM_MEMORY_FILE):
        return "No long-term memories found yet."
    try:
        with open(LONG_TERM_MEMORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if key in data:
                return f"{key}: {data[key]}"
            return f"I don't have a specific memory for '{key}'."
    except Exception:
        return "Error reading memory."

# ==============================================================================
# KNOWLEDGE BASE (RAG) INITIALIZATION
# ==============================================================================

os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(name="jarvis_docs")
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

def ingest_documents() -> None:
    """Ingest local text files and PDFs into the vector database for RAG."""
    from pypdf import PdfReader
    files = os.listdir(KNOWLEDGE_DIR)
    if not files: 
        return
    for filename in files:
        filepath = os.path.join(KNOWLEDGE_DIR, filename)
        text = ""
        if filename.endswith(".txt"):
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f: 
                text = f.read()
        elif filename.endswith(".pdf"):
            reader = PdfReader(filepath)
            for page in reader.pages: 
                text += page.extract_text() or ""
        if text.strip():
            embedding = embedding_model.encode(text).tolist()
            try: 
                collection.upsert(documents=[text], embeddings=[embedding], ids=[f"file_{filename}"])
            except Exception: 
                pass

ingest_documents()

def search_knowledge_base(query: str) -> str:
    """Search local documentation and files for relevant context."""
    query_embedding = embedding_model.encode(query).tolist()
    results = collection.query(query_embeddings=[query_embedding], n_results=3)
    docs = results.get("documents", [[]])[0]
    return "\n---\n".join(docs) if docs else "No relevant information found."

# ==============================================================================
# SYSTEM & UTILITY TOOLSET
# ==============================================================================

APPS = {
    "notepad": "notepad", "calculator": "calc", "chrome": "chrome",
    "edge": "msedge", "explorer": "explorer", "word": "winword",
    "excel": "excel", "powerpoint": "powerpnt", "vscode": "code", "spotify": "spotify", "vlc": "vlc",
}

def open_app(name: str) -> str:
    """Launch a permitted system application."""
    clean_name = name.lower().strip().replace("google", "").strip()
    cmd = APPS.get(clean_name) or APPS.get(name.lower().strip())
    if not cmd: 
        return f"'{name}' is not allowed."
    subprocess.Popen(f'start "" {cmd}', shell=True)
    return f"Opened {name}"

def close_app(name: str) -> str:
    """Terminate a running system application or process."""
    name = name.lower().strip()
    if "chrome" in name or "youtube" in name:
        subprocess.run("taskkill /f /im chrome.exe", shell=True, capture_output=True)
        return "Terminated Google Chrome."
    proc = f"{name}.exe"
    subprocess.run(f"taskkill /f /im {proc}", shell=True, capture_output=True)
    return f"Terminated {name}"

def open_website(url: str) -> str:
    """Open a specific web URL in the default browser."""
    if not url.startswith(("http://", "https://")): 
        url = "https://" + url
    webbrowser.open(url)
    return f"Opened {url}"

def web_search_browser(query: str) -> str:
    """Perform a Google search in the default web browser."""
    webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote(query))
    return f"Searched: {query}"

def play_youtube(query: str) -> str:
    """Search and play a video on YouTube."""
    webbrowser.open(f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}")
    return f"Playing '{query}' on YouTube."

def get_time() -> str:
    """Return current local time and date."""
    return datetime.now().strftime("%A, %d %B %Y, %H:%M")

def control_volume(action: str) -> str:
    """Adjust system audio volume levels or mute status."""
    import pyautogui
    action = action.lower().strip()
    if "mute" in action and "un" not in action:
        pyautogui.press("volumemute")
        return "Volume muted."
    elif "unmute" in action:
        pyautogui.press("volumemute")
        return "Volume unmuted."
    elif "up" in action:
        for _ in range(5): 
            pyautogui.press("volumeup")
        return "Volume increased."
    elif "down" in action:
        for _ in range(5): 
            pyautogui.press("volumedown")
        return "Volume decreased."
    return "Invalid action."

def take_screenshot_and_analyze(prompt: str) -> str:
    """Capture screen and analyze visual content using multimodal vision model."""
    import pyautogui
    screenshot_path = "screenshot_temp.png"
    pyautogui.screenshot().save(screenshot_path)
    try:
        res = ollama.chat(
            model=VISION_MODEL, 
            messages=[{"role": "user", "content": prompt or "Describe screen.", "images": [screenshot_path]}]
        )
        return res.message.content
    except Exception as e: 
        return f"Vision error: {e}"

# Tool registry bindings
TOOL_FUNCS = {
    "open_app": lambda a: open_app(a["name"]),
    "close_app": lambda a: close_app(a["name"]),
    "open_website": lambda a: open_website(a["url"]),
    "web_search_browser": lambda a: web_search_browser(a["query"]),
    "play_youtube": lambda a: play_youtube(a["query"]),
    "get_time": lambda a: get_time(),
    "search_knowledge_base": lambda a: search_knowledge_base(a["query"]),
    "control_volume": lambda a: control_volume(a["action"]),
    "take_screenshot_and_analyze": lambda a: take_screenshot_and_analyze(a.get("prompt", "")),
    "save_to_long_term_memory": lambda a: save_to_long_term_memory(a["key"], a["value"]),
    "read_long_term_memory": lambda a: read_long_term_memory(a["key"]),
}

TOOLS = [
    {"type": "function", "function": {"name": "open_app", "description": "Open app", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "close_app", "description": "Close app", "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}},
    {"type": "function", "function": {"name": "open_website", "description": "Open website", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}},
    {"type": "function", "function": {"name": "web_search_browser", "description": "Search web", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "play_youtube", "description": "Play YouTube", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "get_time", "description": "Get time", "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "search_knowledge_base", "description": "Search docs", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
    {"type": "function", "function": {"name": "control_volume", "description": "Control volume", "parameters": {"type": "object", "properties": {"action": {"type": "string"}}, "required": ["action"]}}},
    {"type": "function", "function": {"name": "take_screenshot_and_analyze", "description": "Vision", "parameters": {"type": "object", "properties": {"prompt": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "save_to_long_term_memory", "description": "Save memory", "parameters": {"type": "object", "properties": {"key": {"type": "string"}, "value": {"type": "string"}}, "required": ["key", "value"]}}},
    {"type": "function", "function": {"name": "read_long_term_memory", "description": "Read memory", "parameters": {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}}},
]

# ==============================================================================
# CORE AI INFERENCE & SPEECH MODULES
# ==============================================================================

def ask_jarvis(user_text: str) -> str:
    """Send user input to local Ollama model and execute tool calls iteratively."""
    messages.append({"role": "user", "content": user_text})
    while True:
        response = ollama.chat(model=MODEL, messages=messages, tools=TOOLS)
        msg = response.message
        messages.append(msg)
        if not msg.tool_calls:
            save_memory(messages)
            return msg.content or ""
        for call in msg.tool_calls:
            name = call.function.name
            args = call.function.arguments
            try: 
                out = TOOL_FUNCS[name](args)
            except Exception as e: 
                out = f"Error: {e}"
            messages.append({"role": "tool", "tool_name": name, "content": out})

def speak(text: str) -> None:
    """Synthesize text into natural English speech using Edge TTS and play audio silently in the background."""
    if not text:
        return
    voice = "en-US-AndrewNeural"  # Strictly English voice
    audio_file = os.path.abspath("temp_edge_voice.mp3")

    async def generate_audio():
        try:
            communicate = edge_tts.Communicate(text, voice)
            await communicate.save(audio_file)
        except Exception as e:
            print(f"TTS Error: {e}")

    try:
        asyncio.run(generate_audio())
        if os.path.exists(audio_file):
            playsound(audio_file)
            try:
                os.remove(audio_file)
            except Exception:
                pass
    except Exception as e:
        print(f"Audio playback error: {e}")

# ==============================================================================
# BACKGROUND SERVICE DAEMON LOOP
# ==============================================================================

def run_background_daemon() -> None:
    """Run continuous background audio monitoring for wake words and continuous voice commands."""
    from faster_whisper import WhisperModel
    import sounddevice as sd
    import numpy as np

    print("==================================================")
    print("⚡ J.A.R.V.I.S. Background Daemon Started ⚡")
    print("Listening quietly in the background... Say 'Jarvis'")
    print("==================================================")

    whisper_model = WhisperModel("base", device="cpu", compute_type="int8")
    samplerate = 16000
    block_duration = 0.1
    block_size = int(samplerate * block_duration)
    energy_threshold = 0.025
    wake_keywords = ["jarvis", "jervis", "جارفيس", "جارڤيس"]
    sleep_keywords = ["goodbye", "stop", "sleep", "nevermind", "go to sleep", "exit"]

    is_active = False

    while True:
        audio_buffer = []
        speech_started = False
        silent_blocks = 0

        with sd.InputStream(samplerate=samplerate, channels=1, dtype='float32') as stream:
            while True:
                audio_chunk, _ = stream.read(block_size)
                audio_flat = audio_chunk.flatten()
                energy = np.sqrt(np.mean(audio_flat**2))

                if energy > energy_threshold:
                    speech_started = True
                    audio_buffer.append(audio_flat)
                    silent_blocks = 0
                elif speech_started:
                    audio_buffer.append(audio_flat)
                    silent_blocks += 1
                    if silent_blocks > 10: 
                        break

        if not audio_buffer: 
            continue

        full_audio = np.concatenate(audio_buffer)
        segments, _ = whisper_model.transcribe(full_audio, beam_size=3, vad_filter=True)
        raw_text = " ".join(s.text for s in segments).strip().lower()

        if not raw_text: 
            continue

        if not is_active:
            if any(w in raw_text for w in wake_keywords):
                is_active = True
                print("\n[Activated] Yes, sir?")
                speak("Yes, sir?")
        else:
            if any(k in raw_text for k in sleep_keywords):
                is_active = False
                print("\n[Standby] Returning to background mode.")
                speak("Going back to standby, sir.")
                continue

            print(f"\n[Command heard] {raw_text}")
            reply = ask_jarvis(raw_text)
            print(f"[JARVIS reply] {reply}")
            speak(reply)
            # Retains active state (is_active = True) for seamless follow-up commands

if __name__ == "__main__":
    run_background_daemon()