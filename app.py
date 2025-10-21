import streamlit as st
import tempfile
import io
import contextlib
from pathlib import Path
from analizar_superficie_con_mapa import main

# =====================================================
# CONFIGURACIÓN DE LA APP STREAMLIT
# =====================================================
st.set_page_config(
    page_title="Analizador de Superficie GPX 🗺️",
    page_icon="🗺️",
    layout="wide"
)

# Variable de estado para saber si ya se generó el mapa
if "map_html" not in st.session_state:
    st.session_state.map_html = None

# =====================================================
# INTERFAZ PRINCIPAL
# =====================================================
if st.session_state.map_html is None:
    st.title("🏍️ Analizador de Superficie GPX")
    st.markdown("""
    Sube un archivo **.GPX** y esta aplicación analizará tu ruta, clasificando tramos como 
    **asfalto**, **offroad** o **desconocido**, y generando un **mapa interactivo** con estadísticas.
    """)

    uploaded_file = st.file_uploader("📂 Sube tu archivo GPX", type=["gpx"])

    if uploaded_file is not None:
        # Guardar archivo temporalmente
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gpx") as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = Path(tmp.name)

        st.info("Procesando el archivo... esto puede tardar unos segundos ⏳")

        # Capturar la salida y el HTML generado
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            html_content = main(str(tmp_path))
        output = buffer.getvalue()

        # Guardar en el estado para mostrar el mapa
        st.session_state.map_html = html_content
        st.session_state.log_output = output

        st.rerun()  # recargar la página para mostrar el mapa
else:
    st.title("🗺️ Resultado del análisis")
    st.components.v1.html(st.session_state.map_html, height=750, scrolling=True)

    with st.expander("📜 Ver registro del análisis"):
        st.text(st.session_state.log_output)

    if st.button("🔁 Analizar otro archivo"):
        st.session_state.map_html = None
        st.session_state.log_output = None
        st.rerun()
