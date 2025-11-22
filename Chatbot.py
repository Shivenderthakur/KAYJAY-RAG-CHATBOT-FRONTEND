# streamlit_rag_client.py

import streamlit as st
import requests
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from dotenv import load_dotenv
from os import getenv

# -- API hygiene: never expose URLs in UI --
load_dotenv()

def get_api_url():
    return getenv("uri")

_API_ROOT = (get_api_url() or "http://localhost:8080").rstrip('/')
_ENDPOINTS = {
    "chat":      _API_ROOT + "/chat",
    "new":       _API_ROOT + "/session/new",
    "history":   _API_ROOT + "/session/history",
    "health":    _API_ROOT + "/health"
}

def server_online():
    try:
        resp = requests.get(_ENDPOINTS["health"], timeout=15)
        return resp.status_code == 200
    except Exception:
        return False

st.set_page_config(page_title="KayJay RAG Chatbot", layout="wide")
st.title("KayJay RAG Chatbot — Professional Assistant")

# STATE
if "chat_session_id" not in st.session_state:
    st.session_state["chat_session_id"] = None
if "history" not in st.session_state:
    st.session_state["history"] = []
if "lead_state" not in st.session_state:
    st.session_state["lead_state"] = {}
if "backend_online" not in st.session_state:
    st.session_state["backend_online"] = server_online()
if "backend_checked" not in st.session_state:
    st.session_state["backend_checked"] = True

# --- Chat input form ---
with st.form(key="chat_form", clear_on_submit=True):
    user_input = st.text_area(
        "Your message:",
        key="user_input",
        height=70,
        max_chars=2000,
        placeholder="Type your message here..."
    )
    submit_btn = st.form_submit_button("Send", use_container_width=True)

def add_to_history(role, text):
    st.session_state["history"].append({"role": role, "content": text})

def render_chat():
    for msg in st.session_state["history"]:
        is_user = msg["role"] == "user"
        with st.chat_message("user" if is_user else "assistant"):
            st.markdown(msg["content"])

# --- Sidebar: Session resume & status ---
with st.sidebar:
    st.header("Session Management")
    session_id_input = st.text_input("Enter Session ID to resume:", key="reconnect_box")
    if st.button("Load Session", use_container_width=True):
        if session_id_input.strip():
            with st.spinner("Loading session..."):
                try:
                    resp = requests.post(
                        _ENDPOINTS["history"],
                        json={"session_id": session_id_input.strip()},
                        timeout=30
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        st.session_state["chat_session_id"] = session_id_input.strip()
                        st.session_state["history"] = data.get("history", [])
                        st.success("Session loaded and chat restored.")
                        st.rerun()
                    elif resp.status_code == 408:
                        st.warning("The server took too long to respond. Please try again after 30-60 seconds.")
                    else:
                        st.error("Session not found or expired.")
                except requests.exceptions.ReadTimeout:
                    st.warning("The server is currently waking up or under heavy load. Please wait and retry your action.")
                except Exception:
                    st.error("Could not connect to server. Please check your internet or retry in a moment.")
    st.markdown("---")
    cur_id = st.session_state.get("chat_session_id", "")
    if cur_id:
        st.markdown("**Current Session ID:**")
        st.code(cur_id, language="text")
        st.info("Please save this Session ID securely to resume your chat later.")
    else:
        st.info("A Session ID will be assigned after your first message. Save it to continue later!")
    st.markdown("---")
    online = st.session_state.get("backend_online")
    col1, col2 = st.columns([1,1])
    col1.markdown(
        "🟢 **Online**" if online else "🔴 **Offline/Sleeping**"
    )
    if col2.button("Refresh Status", use_container_width=True):
        with st.spinner("Checking..."):
            st.session_state["backend_online"] = server_online()
            st.session_state["backend_checked"] = True
        st.rerun()
    st.markdown("---")
    if st.button("Clear Session and Restart", use_container_width=True):
        st.session_state["chat_session_id"] = None
        st.session_state["history"] = []
        st.session_state["lead_state"] = {}
        st.rerun()
    st.caption("KayJay Global Solutions © 2025")

# --- Process message ---
if submit_btn and user_input.strip():
    with st.spinner("Processing..."):
        # Assign session if none
        if not st.session_state["chat_session_id"]:
            try:
                sid_resp = requests.post(_ENDPOINTS["new"], timeout=130)
                if sid_resp.status_code == 200:
                    sid_info = sid_resp.json()
                    st.session_state["chat_session_id"] = sid_info["session_id"]
                else:
                    st.error("Unable to create a session. Try again.")
                    st.stop()
            except requests.exceptions.ReadTimeout:
                st.warning("The backend took too long to respond. Please retry after a short wait.")
                st.stop()
            except Exception:
                st.error("Error connecting to backend. Try later.")
                st.stop()
        try:
            payload = {
                "message": user_input.strip(),
                "session_id": st.session_state["chat_session_id"]
            }
            resp = requests.post(_ENDPOINTS["chat"], json=payload, timeout=500)
            if resp.status_code == 200:
                out = resp.json()
                st.session_state["chat_session_id"] = out.get("session_id", st.session_state["chat_session_id"])
                st.session_state["lead_state"] = out.get("lead_state", {})
                add_to_history("user", user_input.strip())
                add_to_history("assistant", out.get("response", "No response received from assistant."))
                st.info(f"Your Session ID: `{st.session_state['chat_session_id']}` — Save this for future use.")
            elif resp.status_code == 408:
                st.warning("The server is taking longer than expected. Please try again after 30-60 seconds.")
            else:
                add_to_history("assistant", f"Server error [{resp.status_code}]: {resp.text}")
        except requests.exceptions.ReadTimeout:
            add_to_history("assistant", "The assistant is waking up or under high load. Please try again in 30–60 seconds.")
        except Exception:
            add_to_history("assistant", "Failed to connect to backend. Try again later.")
    st.rerun()

# --- Output history ---
st.session_state["history"] = [
    h for h in st.session_state["history"]
    if h["content"] and h["content"].strip()
][-40:]

if st.session_state["history"]:
    st.markdown("---")
    render_chat()
else:
    st.info(
        "Start your chat by sending a message. After the first message, your Session ID will be shown. Save this ID to resume your chat in the future."
    )
