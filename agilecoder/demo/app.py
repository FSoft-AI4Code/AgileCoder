import streamlit as st
import os
import subprocess
import streamlit.components.v1 as components

task_description = st.text_input('Task Description')
project_name = st.text_input('Project Name')

if 'run_button' in st.session_state and st.session_state.run_button == True:
    st.session_state.running = True
else:
    st.session_state.running = False
if st.button('Run', disabled = st.session_state.running, key = 'run_button'):
    subprocess.run(['python3', '../run.py', '--task', task_description, '--name', project_name])
    components.html(
        """
    <link rel="stylesheet" href="https://pyscript.net/latest/pyscript.css" />
    <script defer src="https://pyscript.net/latest/pyscript.js"></script>
    <html>
        <py-script> print('Now you can!') </py-script>

    </html>
        """,
        height=600,
    )
