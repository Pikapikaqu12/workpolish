# app.py
import os
import re
from dotenv import load_dotenv
import streamlit as st
from google import genai

# ---- load env and init client ----
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# If no API key, give a friendly notice in UI and stop
if not API_KEY:
    st.set_page_config(page_title="WorkPolish (Gemini)", layout="centered")
    st.title("✨ WorkPolish — AI Workplace Writing Assistant (Gemini)")
    st.error("Missing GEMINI_API_KEY. Please set GEMINI_API_KEY in environment or Streamlit Secrets.")
    st.stop()

client = genai.Client(api_key=API_KEY)

# ---- page config and simple CSS to force white background & black text ----
st.set_page_config(page_title="WorkPolish (Gemini)", layout="centered")

# CSS: white background, black text, adjust container width and button styles slightly
st.markdown(
    """
    <style>
    /* page background and text color */
    html, body, .stApp {
        background-color: #ffffff;
        color: #000000;
    }
    /* main container background (in case of theming) */
    .css-18e3th9 {  /* Streamlit main block */
        background-color: #ffffff !important;
        color: #000000 !important;
    }
    /* headings and subheaders */
    h1, h2, h3, h4, h5, h6 {
        color: #000000 !important;
    }
    /* style the download button and primary button */
    button[kind="primary"] {
        background-color: #111111 !important;
        color: #ffffff !important;
    }
    /* text area text color */
    textarea, input[type="text"] {
        color: #000000 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---- header ----
st.title("✨ WorkPolish — AI Workplace Writing Assistant (Gemini)")
st.write("Polish your professional emails, chat messages, and slides. Choose tone/context and click 'Polish'.")

# ---- UI components ----
user_text = st.text_area("Enter text to polish:", height=200)
tone = st.selectbox("Target tone", ["More formal", "More concise", "More polite", "More persuasive", "More casual"])
context = st.selectbox("Context", ["Email to manager", "Message to teammate", "Email to client", "PPT text", "Chat message"])
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
    if show_notes:
        prompt += "Output format:\n1) Polished text\n2) 2-3 short bullet points describing key edits\n"
    else:
        prompt += "Output format: Polished text only.\n"
    return prompt

def parse_polished_and_notes(raw: str):
    """
    Try to split model output into polished_text and edit_notes.
    Looks for markers like '1)' and '2)' or '1.' and '2.' or headings.
    Returns (polished_text, edit_notes_list)
    If unable to parse, returns (raw, []).
    """
    text = raw.strip()

    # Try common "1) ... 2) ..." pattern (including newlines)
    m = re.search(r"(?:\n|^)\s*1[\)\.]([\s\S]*?)(?:\n\s*2[\)\.])([\s\S]*)", "\n" + text)
    if m:
        polished = m.group(1).strip()
        notes_raw = m.group(2).strip()
        # split notes into lines; remove numeric bullets if present
        notes = [re.sub(r"^\s*[-\d\.\)]+\s*", "", s).strip() for s in re.split(r"\n+", notes_raw) if s.strip()]
        return polished, notes

    # Try "Polished text:" heading then "Edit notes" heading
    m2 = re.search(r"Polished text[:\-]?\s*(.*?)\s*(?:\n+Edit notes[:\-]?|\n+Key edits[:\-]?|\n+2[\)\.])([\s\S]*)", text, flags=re.I|re.S)
    if m2:
        polished = m2.group(1).strip()
        notes_raw = m2.group(2).strip()
        notes = [s.strip() for s in re.split(r"[\n\r]+", notes_raw) if s.strip()]
        return polished, notes

    # Fallback: try to split by "2)" only
    parts = re.split(r"\n\s*2[\)\.]\s*", text, maxsplit=1)
    if len(parts) == 2:
        # remove any leading "1)" markers from first part
        first = re.sub(r"^\s*1[\)\.]\s*", "", parts[0]).strip()
        notes_raw = parts[1].strip()
        notes = [s.strip() for s in re.split(r"[\n\r]+", notes_raw) if s.strip()]
        return first, notes

    # If nothing matched, return raw as polished and no notes
    return text, []

# ---- action ----
if st.button("Polish ✨"):
    if not user_text.strip():
        st.warning("Please enter some text to polish.")
    else:
        st.info("Calling Gemini...")
        prompt = build_prompt(user_text, tone, context, show_notes)
        try:
            # Use the SDK's models.generate_content method (as in official examples)
            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
            )

            # response.text is preferred; fallback to string of response
            raw_output = response.text if hasattr(response, "text") else str(response)

            # parse into polished and notes
            polished_text, notes = parse_polished_and_notes(raw_output if raw_output else "")

            # show polished result clearly
            st.subheader("✅ Polished result")
            st.markdown(f"```\n{polished_text}\n```")

            # show edit notes if requested and parsed
            if show_notes:
                st.subheader("✏️ Edit notes")
                if notes:
                    for n in notes:
                        st.markdown(f"- {n}")
                else:
                    # if no structured notes, show the tail of raw_output (best effort)
                    # attempt to display lines after polished_text in raw_output
                    # fallback: show entire raw_output under Notes
                    st.write("No structured notes parsed. Raw output:")
                    st.write(raw_output)

            # download button
            st.download_button("Download result (.txt)", data=polished_text, file_name="polished_text.txt", mime="text/plain")

        except Exception as e:
            st.error(f"API call failed: {e}")
            st.write("If this persists, please run `pip install --upgrade google-genai` and restart the app.")
            raise