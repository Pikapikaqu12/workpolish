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
st.markdown(
    """
    <style>
    body, .stApp { background-color: #ffffff !important; color: #000000 !important; }
    textarea, .stTextArea textarea { background-color: #f8f8f8 !important; color: #000000 !important;
        border-radius: 8px !important; border: 1px solid #cccccc !important; font-size: 16px !important; }
    div[data-testid="stMarkdownContainer"] p { color: #000000 !important; }
    div.stButton button, div[data-testid="stDownloadButton"] button {
        background-color: #007bff !important; color: #ffffff !important; border-radius: 8px !important;
        border: none !important; padding: 0.6em 1.2em !important; font-weight: 600 !important; font-size: 16px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.15) !important; transition: all 0.15s ease-in-out; }
    div.stButton button:hover, div[data-testid="stDownloadButton"] button:hover {
        background-color: #0056b3 !important; transform: translateY(-1px); }
    div[data-testid="stDownloadButton"] button::before { content: "⬇️ "; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---- header ----
st.title("✨ WorkPolish — AI Workplace Writing Assistant (Gemini)")
st.write("Polish your professional emails, chat messages, and slides. Choose tone/context and click 'Polish'.")

# ---- UI ----
user_text = st.text_area("Enter text to polish:", height=200)
context = st.selectbox("Context", [
    "Email to manager",
    "Message to manager",
    "Message to teammate",
    "Email to online seller (e.g. Amazon)",
    "PPT text",
    "Chat message"
])
tone = st.selectbox("Target tone", ["More formal", "More concise", "More polite", "More persuasive", "More casual"])
show_notes = st.checkbox("Show edit notes (2-3 bullets)", value=True)

# ---- prompt builder ----
def build_prompt(text: str, tone: str, context: str, show_notes: bool) -> str:
    base = (
        "You are a professional workplace writing assistant. "
        "Polish the text for clarity, tone, and conciseness while keeping the original meaning strictly unchanged.\n\n"
        f"- Target tone: {tone}\n"
        f"- Context: {context}\n"
        "- Do not invent new facts or add content not present in the original text.\n\n"
        "Original:\n\"\"\"\n" + text + "\n\"\"\"\n\n"
    )
    # If context is an email type, ask for a short subject as well
    if "Email" in context:
        base += (
            "Also produce a short email subject line (<= 8 words) on its own line prefixed by 'Subject:'.\n"
            "Then provide the polished email body. "
        )
    if show_notes:
        base += "Output format:\n1) Polished text (or Polished Email body)\n2) 2-3 short bullet points describing key edits\n"
    else:
        base += "Output format: Polished text only.\n"
    return base

# ---- parsing helpers ----
def extract_subject(raw: str):
    """
    Try to extract a Subject line. Returns (subject_or_none, remaining_text).
    Looks for a line starting with 'Subject:' (case-insensitive).
    """
    if not raw:
        return None, raw
    # search for Subject: at start of line
    m = re.search(r"(?im)^(?:Subject|Subject Line)\s*[:\-]\s*(.+)", raw)
    if m:
        subject = m.group(1).strip().strip('"')
        # remove only the first match from raw
        remaining = raw[:m.start()] + raw[m.end():]
        return subject, remaining.strip()
    # try a single-line subject at the very beginning (no label), e.g. "Refund for missing item\n\nDear..."
    first_line = raw.strip().splitlines()
    if len(first_line) > 0 and len(first_line[0].split()) <= 8:
        # Heuristic: if first line is short (< =8 words) and followed by blank line, treat as subject
        lines = raw.splitlines()
        if len(lines) > 1 and lines[1].strip() == "":
            subject = lines[0].strip().strip('"')
            remaining = "\n".join(lines[2:]).strip()
            return subject, remaining
    return None, raw

def parse_polished_and_notes(raw: str):
    """
    Try to split model output into polished_text and edit_notes list.
    """
    text = raw.strip()
    # pattern: 1) ... 2) ...
    m = re.search(r"(?:\n|^)\s*1[\)\.]([\s\S]*?)(?:\n\s*2[\)\.])([\s\S]*)", "\n" + text)
    if m:
        polished = m.group(1).strip()
        notes_raw = m.group(2).strip()
        notes = [re.sub(r"^\s*[-\d\.\)]+\s*", "", s).strip() for s in re.split(r"\n+", notes_raw) if s.strip()]
        return polished, notes
    # fallback split by "2)"
    parts = re.split(r"\n\s*2[\)\.]\s*", text, maxsplit=1)
    if len(parts) == 2:
        first = re.sub(r"^\s*1[\)\.]\s*", "", parts[0]).strip()
        notes = [s.strip() for s in re.split(r"[\n\r]+", parts[1]) if s.strip()]
        return first, notes
    # fallback: no notes
    return text, []

# ---- action ----
if st.button("Polish ✨"):
    if not user_text.strip():
        st.warning("Please enter some text to polish.")
    else:
        st.info("Calling Gemini...")
        prompt = build_prompt(user_text, tone, context, show_notes)
        try:
            response = client.models.generate_content(model=MODEL, contents=prompt)
            raw_output = response.text if hasattr(response, "text") else str(response)

            # 1) extract subject if email context
            subject, remaining = (None, raw_output)
            if "Email" in context:
                subject, remaining = extract_subject(raw_output)

            # 2) parse polished text and notes from remaining
            polished_text, notes = parse_polished_and_notes(remaining)

            # 3) clean polished_text (strip quotes and surrounding whitespace)
            polished_text = polished_text.strip().strip('"')

            # ---- display Subject if present ----
            if subject:
                st.subheader("✉️ Subject")
                st.markdown(f"**{subject}**")

            # ---- display polished email/text ----
            st.subheader("✅ Polished result")
            # show as disabled text_area (no label) to preserve wrapping and allow easy copy/select
            st.text_area(label="", value=polished_text, height=200, key="polished_result", disabled=True)

            # ---- display edit notes if requested ----
            if show_notes:
                st.subheader("✏️ Edit notes")
                if notes:
                    for n in notes:
                        st.markdown(f"- {n}")
                else:
                    st.write("No structured notes parsed. Raw output:")
                    st.write(raw_output)

            # ---- download button ----
            st.download_button("⬇️ Download result", data=polished_text, file_name="polished_text.txt", mime="text/plain", key="download_result")

        except Exception as e:
            st.error(f"API call failed: {e}")
            st.write("If this persists, please run `pip install --upgrade google-genai` and restart the app.")
            raise