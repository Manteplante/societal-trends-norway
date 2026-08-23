"""Landing page — what the dashboard opens on."""

import streamlit as st

from backend import config
from backend import storage

st.title(f"{config.APP_ICON} {config.APP_NAME}")
st.caption("A Streamlit app showcasing societal trends in Norway. Built with the `streamlit-template` and ssb python wrapper.")

frontpage = config.ROOT / "assets" / "frontpage.png"
if frontpage.exists():
    st.image(str(frontpage))
    st.caption(
        "Image generated with OpenAI. Prompt: “Create an animated frontpage picture, "
        "using Samurai Champloo anime style but with a casual viking warrior instead of "
        "samurai, and quite minimalistic mountains and a fiord showcasing national "
        "societal insights; elderly care, population growth, health”"
    )
