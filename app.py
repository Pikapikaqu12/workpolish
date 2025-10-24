import os
from dotenv import load_dotenv
import streamlit as st
from google import genai
import re

# Load environment variables
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Initialize client
client = genai.Client(api_key=API_KEY) if API_KEY else genai.Client()

st.set_page_config(page_title="WorkPolish (Gemini)", layout="centered")

# ---- custom CSS ----
st.markdown("""
<style>
body, .stApp {
    background-color: #ffffff !important;
    color: #000000 !important;
}

/* Text area styling */
textarea, .stTextArea textarea {
    background-color: #f8f8f8 !important;
    color: #000000 !important;
    border-radius: 8px !important;
    border: 1px solid #cccccc !important;
    font-size: 16px !important;
    caret-color: #000000 !important;
}

/* Subject box */
.subject-box {
    background-color: #e6f2ff;
    padding: 0.6em 1em;
    border-left: 4px solid #007bff;
    border-radius: 5px;
    margin-bottom: 1em;
}

/* Buttons (Polish + Download) */
div.stButton button, div[data-testid="stDownloadButton"] button {
    background-color: #007bff !important;
    color: #ffffff !important;
    border-radius: 8px !important;
    border: none !important;
    padding: 0.6em 1.2em !important;
    font-weight: 600 !important;
    font-size: 16px !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.15) !important;
    transition: all 0.2s ease-in-out;
}
div.stButton button:hover, div[data-testid="stDownloadButton"] button:hover {
    background-color: #0056b3 !important;
    transform: translateY(-1px);
}
div[data-testid="stDownloadButton"] button::before { content: "⬇️ "; }
</style>
""", unsafe_allow_html=True)

# ---- header ----
st.title("✨ WorkPolish — AI Workplace Writing Assistant (Gemini)")
st.write("Polish your professional emails, chat messages, and slides. Choose tone/context and click 'Polish'.")

# ---- UI components ----
user_text = st.text_area("Enter text to polish:", height=200, placeholder="Type or paste your text here...")
tone = st.selectbox("Target tone", ["More formal", "More concise", "More polite", "More persuasive", "More casual"])
context = st.selectbox("Context", [
    "Email to manager",
    "Message to manager",
    "Message to teammate",
    "Email to online seller (e.g. Amazon)",
    "PPT text",
    "Chat message"
])
show_notes = st.checkbox("Show edit notes (2-3 bullets)", value=True)

# ---- prompt builder ----
def build_prompt(text: str, tone: str, context: str, show_notes: bool) -> str:
    prompt = (
        "You are a professional workplace writing assistant. "
        "Polish the text for clarity, tone, and conciseness while keeping the original meaning strictly unchanged.\n\n"
        f"- Target tone: {tone}\n"
        f"- Context: {context}\n"
        f"- Do not invent new facts or add content not present in the original text.\n\n"
        f"Original:\n\"\"\"\n{text}\n\"\"\"\n\n"
    )
    if "Email" in context:
        prompt += "Also produce a short email subject line (<= 8 words) prefixed by 'Subject:'. Then provide the polished email body.\n\n"
    if show_notes:
        prompt += "Output format:\n1) Polished text (or email body)\n2) 2-3 short bullet points describing key edits\n"
    else:
        prompt += "Output format: Polished text only.\n"
    return prompt

# ---- parsing functions ----
def parse_polished_and_notes(raw: str):
    text = (raw or "").strip()
    m = re.search(r"(?:\n|^)\s*1[\)\.]([\s\S]*?)(?:\n\s*2[\)\.])([\s\S]*)", "\n"+text)
    if m:
        polished = m.group(1).strip()
        notes_raw = m.group(2).strip()
        notes = [re.sub(r"^\s*[-\d\.\)]+\s*", "", s).strip() for s in re.split(r"\n+", notes_raw) if s.strip()]
        return polished, notes
    parts = re.split(r"\n\s*2[\)\.]\s*", text, maxsplit=1)
    if len(parts) == 2:
        first = re.sub(r"^\s*1[\)\.]\s*", "", parts[0]).strip()
        notes = [s.strip() for s in re.split(r"[\n\r]+", parts[1]) if s.strip()]
        return first, notes
    return text, []

def extract_subject(raw: str):
    if not raw: return None, raw
    m = re.search(r"(?im)^(?:Subject|Subject Line)\s*[:\-]\s*(.+)$", raw, flags=re.M)
    if m:
        subject = m.group(1).strip().strip('"')
        start, end = m.span()
        remaining = (raw[:start] + raw[end:]).strip()
        return subject, remaining
    lines = raw.strip().splitlines()
    if len(lines) > 1 and len(lines[0].split()) <= 8 and lines[1].strip() == "":
        subject = lines[0].strip().strip('"')
        remaining = "\n".join(lines[2:]).strip()
        return subject, remaining
    return None, raw

# ---- action ----
if st.button("Polish ✨"):
    if not user_text.strip():
        st.warning("Please enter some text to polish.")
    else:
        with st.spinner("Calling Gemini..."):
            prompt = build_prompt(user_text, tone, context, show_notes)
            try:
                response = client.models.generate_content(model=MODEL, contents=prompt)
                raw_output = response.text if hasattr(response, "text") else str(response)
                raw_output = (raw_output or "").strip()

                subject = None
                remaining = raw_output
                if "Email" in context and raw_output:
                    subject, remaining = extract_subject(raw_output)

                polished_text, notes = parse_polished_and_notes(remaining)
                cleaned = (polished_text or "").strip().strip('"')

                # ---- Subject display ----
                if subject:
                    st.subheader("✉️ Subject")
                    st.markdown(f"<div class='subject-box'>{subject}</div>", unsafe_allow_html=True)

                # ---- Polished result ----
                st.subheader("✅ Polished result")
                st.text_area(label="", value=cleaned, height=200, max_chars=None, key="polished_text")

                # ---- Edit notes in expander ----
                if show_notes:
                    with st.expander("✏️ Edit notes"):
                        if notes:
                            for n in notes:
                                st.markdown(f"- {n}")
                        else:
                            if raw_output != cleaned:
                                st.write("Notes / Raw output:")
                                st.write(raw_output)
                            else:
                                st.write("No structured notes parsed.")

                # ---- Download button ----
                st.download_button("Download result (.txt)", data=cleaned, file_name="polished_text.txt", mime="text/plain", key="download_result")

            except Exception as e:
                st.error(f"API call failed: {e}")
                st.write("If this persists, please run `pip install --upgrade google-genai` and restart the app.")
                raise