// script.js — conversation flow, recording, API wiring for the demo

let sessionId = null;
let questions = [];
let currentIndex = 0;
let language = "en";
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;

const setupCard = document.getElementById("setupCard");
const conversationCard = document.getElementById("conversationCard");
const resultCard = document.getElementById("resultCard");
const questionText = document.getElementById("question-text");
const progressDots = document.getElementById("progressDots");
const recordBtn = document.getElementById("recordBtn");
const textFallback = document.getElementById("textFallback");
const submitTextBtn = document.getElementById("submitTextBtn");
const statusEl = document.getElementById("status");
const transcriptBox = document.getElementById("transcriptBox");
const recList = document.getElementById("recList");
const ttsAudio = document.getElementById("ttsAudio");
const playRecBtn = document.getElementById("playRecBtn");

document.getElementById("startBtn").addEventListener("click", startSession);
document.getElementById("restartBtn").addEventListener("click", () => location.reload());
recordBtn.addEventListener("click", toggleRecording);
submitTextBtn.addEventListener("click", () => submitAnswer({ mode: "text" }));
playRecBtn.addEventListener("click", playRecommendation);

async function startSession() {
  language = document.getElementById("langSelect").value;
  const res = await fetch("/api/session/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ language }),
  });
  const data = await res.json();
  sessionId = data.session_id;
  questions = data.questions;
  currentIndex = 0;

  setupCard.classList.add("hidden");
  conversationCard.classList.remove("hidden");
  renderProgress();
  showQuestion();
}

function renderProgress() {
  progressDots.innerHTML = "";
  questions.forEach((_, i) => {
    const dot = document.createElement("div");
    dot.className = "dot" + (i < currentIndex ? " done" : i === currentIndex ? " active" : "");
    progressDots.appendChild(dot);
  });
}

function showQuestion() {
  if (currentIndex >= questions.length) {
    finishInterview();
    return;
  }
  renderProgress();
  questionText.textContent = `Q${currentIndex + 1}. ${questions[currentIndex].text}`;
  transcriptBox.textContent = "Transcript will appear here…";
  textFallback.value = "";
  statusEl.textContent = "";
}

async function toggleRecording() {
  if (!isRecording) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunks = [];
      mediaRecorder = new MediaRecorder(stream);
      mediaRecorder.ondataavailable = (e) => audioChunks.push(e.data);
      mediaRecorder.onstop = () => submitAnswer({ mode: "audio" });
      mediaRecorder.start();
      isRecording = true;
      recordBtn.classList.add("recording");
      recordBtn.textContent = "⏹ Stop Recording";
      statusEl.textContent = "Recording… click again to stop.";
    } catch (err) {
      statusEl.textContent = "Mic unavailable — please use the text fallback below.";
    }
  } else {
    mediaRecorder.stop();
    mediaRecorder.stream.getTracks().forEach((t) => t.stop());
    isRecording = false;
    recordBtn.classList.remove("recording");
    recordBtn.textContent = "🎤 Hold / Click to Record";
  }
}

async function submitAnswer({ mode }) {
  const questionId = questions[currentIndex].id;
  statusEl.textContent = "Transcribing…";

  let res;
  if (mode === "audio") {
    const blob = new Blob(audioChunks, { type: "audio/webm" });
    const form = new FormData();
    form.append("audio", blob, "answer.webm");
    form.append("language", language);
    form.append("question_id", questionId);
    form.append("session_id", sessionId);
    res = await fetch("/transcribe", { method: "POST", body: form });
  } else {
    const text = textFallback.value.trim();
    if (!text) { statusEl.textContent = "Please type an answer."; return; }
    res = await fetch("/transcribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, question_id: questionId, session_id: sessionId }),
    });
  }

  const data = await res.json();
  if (data.error) {
    statusEl.textContent = "Voice transcription failed — please type your answer instead.";
    return;
  }
  const engineTag = data.stt_engine && data.stt_engine !== "text_input" ? ` [${data.stt_engine}]` : "";
  transcriptBox.textContent = `"${data.transcript}"${engineTag}  →  extracted: ${data.extracted_value}`;
  if (data.low_confidence) {
    statusEl.textContent = "Not sure we heard that clearly — you can re-record this answer, or continue.";
  } else {
    statusEl.textContent = "Answer recorded ✓";
  }
  currentIndex += 1;
  setTimeout(showQuestion, 700);
}

async function finishInterview() {
  conversationCard.classList.add("hidden");
  const res = await fetch("/api/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  const data = await res.json();
  renderRecommendations(data.recommendations);
  resultCard.classList.remove("hidden");
  window._lastRecommendations = data.recommendations;
}

function renderRecommendations(recs) {
  recList.innerHTML = "";
  recs.forEach((r, i) => {
    const div = document.createElement("div");
    div.className = "rec-card";
    div.innerHTML = `<h3>#${i + 1}. ${r.trade_name} <span class="score-pill">match score ${r.score}</span></h3>
      <div class="muted">${r.category}</div>
      <p>${r.description}</p>`;
    recList.appendChild(div);
  });
}

async function playRecommendation() {
  const recs = window._lastRecommendations || [];
  if (!recs.length) return;
  const summary = `Based on your answers, here are your top recommended training programs. ` +
    recs.map((r, i) => `Number ${i + 1}: ${r.trade_name}.`).join(" ");
  playRecBtn.textContent = "Generating audio…";
  const res = await fetch("/speak", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: summary, language }),
  });
  if (!res.ok) { playRecBtn.textContent = "🔊 Audio failed — try again"; return; }
  const blob = await res.blob();
  ttsAudio.src = URL.createObjectURL(blob);
  ttsAudio.classList.remove("hidden");
  ttsAudio.play();
  playRecBtn.textContent = "🔊 Play Recommendation Aloud";
}
