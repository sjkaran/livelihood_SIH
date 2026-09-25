import customtkinter as ctk
import whisper   # STT
import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import threading
import queue
import tempfile
import os
import pandas as pd
from tkinter import ttk

# Windows TTS Imports
import win32com.client # TTS
import pythoncom

# --- Configuration ---
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")
SAMPLE_RATE = 16000

# ==========================================
# BACKEND MODULES
# ==========================================

class Database:
    def __init__(self):
        self.records = []

    def save_beneficiary(self, name, age, location, recommended_trade):
        self.records.append({
            "Name": name, 
            "Age": age, 
            "Location": location, 
            "Recommended Trade": recommended_trade
        })

    def get_all_records(self):
        return pd.DataFrame(self.records)

class Recommender:
    def __init__(self):
        self.trades = ["Tailoring", "Carpentry", "Computer Data Entry", "Masonry", "Electrician"]

    def predict_trade(self, user_data):
        import random
        return random.choice(self.trades)

class AudioEngine:
    def __init__(self, update_ui_callback):
        self.update_ui = update_ui_callback
        self.model = None
        
        # Audio Queue
        self.is_recording = False
        self.audio_queue = queue.Queue()
        self.audio_data = []

    def load_whisper(self):
        self.update_ui("Loading Whisper AI... (This may take a moment)", "orange")
        self.model = whisper.load_model("base") 
        self.update_ui("System Ready", "green")

    def speak(self, text, lang="english"):
        def _speak():
            # Initialize COM for this background thread to prevent lockups
            pythoncom.CoInitialize()
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            speaker.Speak(text)
            
        threading.Thread(target=_speak, daemon=True).start()

    def transcribe(self, audio_np, target_lang):
        try:
            temp_dir = tempfile.gettempdir()
            temp_file = os.path.join(temp_dir, "pm_ajay_temp.wav")
            wav.write(temp_file, SAMPLE_RATE, audio_np)

            whisper_lang = "en"
            if target_lang == "Hindi": whisper_lang = "hi"
            if target_lang == "Odia": whisper_lang = "or"

            result = self.model.transcribe(temp_file, fp16=False, language=whisper_lang)
            os.remove(temp_file)
            return result["text"].strip()
        except Exception as e:
            print(f"Transcription error: {e}")
            return None

# ==========================================
# FRONTEND UI
# ==========================================

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PM-AJAY Livelihood System")
        self.geometry("900x600")

        self.db = Database()
        self.recommender = Recommender()
        self.audio = AudioEngine(self.update_status)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.setup_sidebar()
        self.setup_assistant_view()
        self.setup_dashboard_view()

        self.current_step = 0
        self.form_data = {"Name": "", "Age": "", "Location": ""}
        
        threading.Thread(target=self.audio.load_whisper, daemon=True).start()

    def setup_sidebar(self):
        self.sidebar_frame = ctk.CTkFrame(self, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(4, weight=1)

        ctk.CTkLabel(self.sidebar_frame, text="PM-AJAY", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, padx=20, pady=(20, 10))

        self.nav_assistant = ctk.CTkButton(self.sidebar_frame, text="Voice Assistant", command=self.show_assistant)
        self.nav_assistant.grid(row=1, column=0, padx=20, pady=10)

        self.nav_dashboard = ctk.CTkButton(self.sidebar_frame, text="Dashboard", command=self.show_dashboard)
        self.nav_dashboard.grid(row=2, column=0, padx=20, pady=10)

        ctk.CTkLabel(self.sidebar_frame, text="Select Language:").grid(row=5, column=0, padx=20, pady=(10, 0))
        self.lang_var = ctk.StringVar(value="English")
        self.lang_menu = ctk.CTkOptionMenu(self.sidebar_frame, values=["English", "Hindi", "Odia"], variable=self.lang_var)
        self.lang_menu.grid(row=6, column=0, padx=20, pady=(5, 20))

    def setup_assistant_view(self):
        self.assistant_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        
        self.chat_display = ctk.CTkTextbox(self.assistant_frame, width=600, height=350, font=ctk.CTkFont(size=14))
        self.chat_display.pack(pady=20)
        self.chat_display.configure(state="disabled")

        self.status_label = ctk.CTkLabel(self.assistant_frame, text="Initializing...", font=ctk.CTkFont(size=14))
        self.status_label.pack(pady=5)

        self.record_btn = ctk.CTkButton(self.assistant_frame, text="🎤 Start Talking", width=200, height=50, command=self.toggle_recording)
        self.record_btn.pack(pady=10)
        
        self.start_interview_btn = ctk.CTkButton(self.assistant_frame, text="Start New Application", fg_color="green", hover_color="darkgreen", command=self.start_interview)
        self.start_interview_btn.pack(pady=10)

        self.assistant_frame.grid(row=0, column=1, sticky="nsew")

    def setup_dashboard_view(self):
        self.dashboard_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        ctk.CTkLabel(self.dashboard_frame, text="Beneficiary Dashboard", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=20)

        columns = ("Name", "Age", "Location", "Recommended Trade")
        self.tree = ttk.Treeview(self.dashboard_frame, columns=columns, show="headings", height=15)
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=150)
            
        self.tree.pack(pady=10, padx=20, fill="both", expand=True)

    def show_assistant(self):
        self.dashboard_frame.grid_forget()
        self.assistant_frame.grid(row=0, column=1, sticky="nsew")

    def show_dashboard(self):
        self.assistant_frame.grid_forget()
        self.dashboard_frame.grid(row=0, column=1, sticky="nsew")
        self.refresh_dashboard()

    def refresh_dashboard(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        df = self.db.get_all_records()
        if not df.empty:
            for _, row in df.iterrows():
                self.tree.insert("", "end", values=list(row))

    def update_status(self, text, color="white"):
        self.status_label.configure(text=text, text_color=color)

    def append_chat(self, sender, message):
        self.chat_display.configure(state="normal")
        self.chat_display.insert("end", f"{sender}: {message}\n\n")
        self.chat_display.see("end")
        self.chat_display.configure(state="disabled")

    def start_interview(self):
        self.current_step = 0
        self.form_data = {"Name": "", "Age": "", "Location": ""}
        self.chat_display.configure(state="normal")
        self.chat_display.delete("1.0", "end")
        self.chat_display.configure(state="disabled")
        self.ask_question()

    def get_questions(self):
        lang = self.lang_var.get()
        if lang == "Hindi":
            return ["पीएम-अजय में आपका स्वागत है। आपका नाम क्या है?", "आपकी उम्र क्या है?", "आप किस गांव से हैं?"]
        elif lang == "Odia":
            return ["ପିଏମ୍-ଅଜୟକୁ ସ୍ୱାଗତ । ଆପଣଙ୍କ ନାମ କଣ?", "ଆପଣଙ୍କ ବୟସ କେତେ?", "ଆପଣ କେଉଁ ଗ୍ରାମରୁ ଆସିଛନ୍ତି?"]
        return ["Welcome to PM-AJAY. What is your name?", "What is your age?", "Which village are you from?"]

    def ask_question(self):
        questions = self.get_questions()
        if self.current_step < len(questions):
            q = questions[self.current_step]
            self.append_chat("System", q)
            self.audio.speak(q, self.lang_var.get())
        else:
            self.finalize_application()

    def finalize_application(self):
        self.update_status("Processing Recommendation...", "yellow")
        trade = self.recommender.predict_trade(self.form_data)
        self.db.save_beneficiary(self.form_data["Name"], self.form_data["Age"], self.form_data["Location"], trade)
        
        msg = f"Application complete. Based on your profile, we recommend training in: {trade}"
        self.append_chat("System", msg)
        self.audio.speak(msg)
        self.update_status("Application Saved to Dashboard", "green")

    def audio_callback(self, indata, frames, time, status):
        if self.audio.is_recording:
            self.audio.audio_queue.put(indata.copy())

    def toggle_recording(self):
        if self.audio.model is None: return
        
        if not self.audio.is_recording:
            self.audio.is_recording = True
            self.audio.audio_data = []
            self.record_btn.configure(text="⏹ Stop", fg_color="red")
            self.update_status("Listening...", "orange")
            self.stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='int16', callback=self.audio_callback)
            self.stream.start()
        else:
            self.audio.is_recording = False
            self.stream.stop()
            self.stream.close()
            self.record_btn.configure(text="Processing...", state="disabled", fg_color="gray")
            self.update_status("Transcribing...", "yellow")
            
            while not self.audio.audio_queue.empty():
                self.audio.audio_data.append(self.audio.audio_queue.get())
            
            if self.audio.audio_data:
                audio_np = np.concatenate(self.audio.audio_data, axis=0)
                threading.Thread(target=self.process_audio, args=(audio_np,), daemon=True).start()

    def process_audio(self, audio_np):
        text = self.audio.transcribe(audio_np, self.lang_var.get())
        self.after(0, self.handle_transcription, text)

    def handle_transcription(self, text):
        self.record_btn.configure(text="🎤 Start Talking", state="normal", fg_color=["#3a7ebf", "#1f538d"])
        self.update_status("Ready", "green")
        
        if not text: return
        
        self.append_chat("Beneficiary", text)
        keys = list(self.form_data.keys())
        if self.current_step < len(keys):
            self.form_data[keys[self.current_step]] = text
            self.current_step += 1
            self.ask_question()

if __name__ == "__main__":
    app = App()
    app.mainloop()