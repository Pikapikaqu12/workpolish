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

/* General text */
div[data-testid="stMarkdownContainer"] p {
    color: #000000 !important;
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
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.15) !important;
    transition: all 0.2s ease-in-out;
}

div.stButton button:hover, div[data-testid="stDownloadButton"] button:hover {
    background-color: #0056b3 !important;
    transform: translateY(-1px);
}

/* Make buttons look distinct but aligned */
div[data-testid="stDownloadButton"] button::before {
    content: "⬇️ ";
}
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

def build_prompt(text: str, tone: str, context: str, show_notes: bool) -> str:
    prompt = (
        "You are a professional workplace writing assistant. "
        "Polish the text for clarity, tone, and conciseness while keeping the original meaning strictly unchanged.\n\n"
        f"- Target tone: {tone}\n"
        f"- Context: {context}\n"
        f"- Do not invent new facts or add content not present in the original text.\n\n"
        f"Original:\n\"\"\"\n{text}\n\"\"\"\n\n"
    )
    # If context is email-like, ask model to also produce a short Subject line prefixed by "Subject:"
    if "Email" in context:
        prompt += (
            "Also produce a short email subject line (<= 8 words) on its own line prefixed by 'Subject:'.\n"
            "Then provide the polished email body.\n\n"
        )
    if show_notes:
        prompt += "Output format:\n1) Polished text (or Polished Email body)\n2) 2-3 short bullet points describing key edits\n"
    else:
        prompt += "Output format: Polished text only.\n"
    return prompt

def parse_polished_and_notes(raw: str):
    """
    Try to split model output into polished_text and edit_notes.
    Returns (polished_text, notes_list).
    If not parseable, returns (raw, []).
    """
    text = (raw or "").strip()

    # Try common "1) ... 2) ..." pattern
    m = re.search(r"(?:\n|^)\s*1[\)\.]([\s\S]*?)(?:\n\s*2[\)\.])([\s\S]*)", "\n" + text)
    if m:
        polished = m.group(1).strip()
        notes_raw = m.group(2).strip()
        notes = [re.sub(r"^\s*[-\d\.\)]+\s*", "", s).strip() for s in re.split(r"\n+", notes_raw) if s.strip()]
        return polished, notes

    # Try headings like "Polished text:" then notes
    m2 = re.search(r"Polished text[:\-]?\s*(.*?)\s*(?:\n+Edit notes[:\-]?|\n+Key edits[:\-]?|\n+2[\)\.])([\s\S]*)", text, flags=re.I|re.S)
    if m2:
        polished = m2.group(1).strip()
        notes_raw = m2.group(2).strip()
        notes = [s.strip() for s in re.split(r"[\n\r]+", notes_raw) if s.strip()]
        return polished, notes

    # Fallback: split by "2)"
    parts = re.split(r"\n\s*2[\)\.]\s*", text, maxsplit=1)
    if len(parts) == 2:
        first = re.sub(r"^\s*1[\)\.]\s*", "", parts[0]).strip()
        notes = [s.strip() for s in re.split(r"[\n\r]+", parts[1]) if s.strip()]
        return first, notes

    # Nothing matched => return raw as polished_text
    return text, []

def extract_subject(raw: str):
    """
    Extract a 'Subject:' line if present (case-insensitive).
    Returns (subject_or_None, remaining_text).
    """
    if not raw:
        return None, raw
    # 1) look for explicit 'Subject:' line
    m = re.search(r"(?im)^(?:Subject|Subject Line)\s*[:\-]\s*(.+)$", raw, flags=re.M)
    if m:
        subject = m.group(1).strip().strip('"')
        # remove only the first Subject line from the raw output
        start, end = m.span()
        remaining = (raw[:start] + raw[end:]).strip()
        return subject, remaining

    # 2) heuristic: if first line is short (<=8 words) and followed by blank line, treat as subject
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
        st.info("Calling Gemini...")
        prompt = build_prompt(user_text, tone, context, show_notes)
        try:
            # call the model
            response = client.models.generate_content(model=MODEL, contents=prompt)

            # robustly extract text from various response shapes
            raw_output = ""
            if hasattr(response, "text") and response.text:
                raw_output = response.text
            elif hasattr(response, "output") and isinstance(response.output, list) and len(response.output) > 0:
                try:
                    raw_output = response.output[0].content[0].text
                except Exception:
                    raw_output = str(response.output)
            elif hasattr(response, "candidates") and isinstance(response.candidates, list) and len(response.candidates) > 0:
                try:
                    raw_output = response.candidates[0].content[0].text
                except Exception:
                    raw_output = str(response.candidates)
            else:
                raw_output = str(response)

            raw_output = (raw_output or "").strip()

            # If email context, extract subject
            subject = None
            remaining = raw_output
            if "Email" in context and raw_output:
                subject, remaining = extract_subject(raw_output)

            # Parse polished text and notes from remaining text
            polished_text, notes = parse_polished_and_notes(remaining)

            # ---------- CLEANUP: ensure notes are not part of polished_text ----------
            # If polished_text likely still contains notes, split it off at common separators.
            # Split at '2)', '2.', 'Edit notes', 'Key edits', or a line that starts with '-' or '*'
            split_re = re.compile(r"(\n\s*2[\)\.]|\n\s*Edit notes[:\-]?|\n\s*Key edits[:\-]?|\n\s*(?:-|\*)(?:\s|$))", flags=re.I)
            parts = split_re.split(polished_text or "")
            if parts and len(parts) > 0:
                # parts[0] is the text before any recognized note marker
                polished_before = parts[0].strip()
                if polished_before:
                    polished_text = polished_before

                # if notes empty, try to capture the trailing part as notes
                if (not notes or len(notes) == 0) and len(parts) > 1:
                    trailing = "".join(parts[1:]).strip()
                    # split trailing by lines and clean bullet markers
                    candidate_notes = [re.sub(r"^\s*[-\*\d\.\)\(]+\s*", "", s).strip()
                                       for s in re.split(r"[\n\r]+", trailing) if s.strip()]
                    if candidate_notes:
                        notes = candidate_notes

            # Fallbacks if polished_text empty
            if not polished_text or polished_text.strip() == "":
                # prefer the 'remaining' chunk (which is raw_output without subject)
                if remaining and remaining.strip():
                    # remove potential trailing notes from remaining as above
                    rem_parts = split_re.split(remaining)
                    polished_text = rem_parts[0].strip() if rem_parts else remaining.strip()
                    # and set notes from trailing if empty
                    if (not notes or len(notes) == 0) and len(rem_parts) > 1:
                        trailing = "".join(rem_parts[1:]).strip()
                        notes = [re.sub(r"^\s*[-\*\d\.\)\(]+\s*", "", s).strip()
                                 for s in re.split(r"[\n\r]+", trailing) if s.strip()]
                elif raw_output:
                    # last resort: take raw_output but strip notes
                    raw_parts = split_re.split(raw_output)
                    polished_text = raw_parts[0].strip() if raw_parts else raw_output.strip()
                    if (not notes or len(notes) == 0) and len(raw_parts) > 1:
                        trailing = "".join(raw_parts[1:]).strip()
                        notes = [re.sub(r"^\s*[-\*\d\.\)\(]+\s*", "", s).strip()
                                 for s in re.split(r"[\n\r]+", trailing) if s.strip()]
                else:
                    polished_text = str(response).strip()

            # Clean final polished_text
            cleaned = (polished_text or "").strip().strip('"')

            # ---- display Subject if present ----
            if subject:
                st.subheader("✉️ Subject")
                st.markdown(f"**{subject}**")

            # ---- display polished email/text (no label inside text_area) ----
            st.subheader("✅ Polished result")
            st.text_area(label="", value=cleaned, height=200, max_chars=None, key="polished_text")

            # ---- display edit notes if requested ----
            if show_notes:
                st.subheader("✏️ Edit notes")
                if notes:
                    for n in notes:
                        st.markdown(f"- {n}")
                else:
                    # if still no parsed notes but raw_output contains extra info, show a short fallback
                    if raw_output and raw_output != cleaned:
                        st.write("Notes / Raw output:")
                        st.write(raw_output)
                    else:
                        st.write("No structured notes parsed.")

            # ---- download button ----
            st.download_button("Download result (.txt)", data=cleaned, file_name="polished_text.txt", mime="text/plain", key="download_result")

        except Exception as e:
            st.error(f"API call failed: {e}")
            st.write("If this persists, please run `pip install --upgrade google-genai` and restart the app.")
            raise