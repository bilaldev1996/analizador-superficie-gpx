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

st.title("🏍️ Analizador de Superficie GPX")
st.markdown("""
Esta herramienta analiza un archivo **GPX** y clasifica la ruta en tramos **asfaltados**, **offroad** o **desconocidos**, 
generando un mapa interactivo con estadísticas de superficie.
""")

uploaded_file = st.file_uploader("📂 Sube tu archivo GPX", type=["gpx"])

if uploaded_file is not None:
    # Guardar archivo temporalmente
    with tempfile.NamedTemporaryFile(delete=False, suffix=".gpx") as tmp:
        tmp.write(uploaded_file.read())
        tmp_path = Path(tmp.name)

    st.success(f"Archivo cargado: {uploaded_file.name}")
    st.info("Procesando el archivo... esto puede tardar unos segundos ⏳")

    # Ejecutar el análisis y capturar salida
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        main(str(tmp_path))
    output = buffer.getvalue()

    with st.expander("📜 Ver registro del análisis"):
        st.text(output)

    # Buscar el HTML generado (mismo directorio que el GPX temporal)
    # Buscar el HTML generado (en la carpeta del proyecto)
    map_filename = f"mapa_ruta_v9_{tmp_path.stem}.html"

    # 1️⃣ Buscar junto al GPX temporal
    map_path = tmp_path.parent / map_filename

    # 2️⃣ Si no existe, buscar en el directorio del proyecto (donde Streamlit guarda los scripts)
    if not map_path.exists():
        project_dir = Path(__file__).parent
        alt_path = project_dir / map_filename
        if alt_path.exists():
            map_path = alt_path

    if map_path.exists():
        with open(map_path, "r", encoding="utf-8") as f:
            html = f.read()


        st.success("✅ Análisis completado. Aquí tienes el mapa:")
        st.components.v1.html(html, height=750, scrolling=True)

        # Descargar el mapa
        with open(map_path, "rb") as f:
            st.download_button(
                label="💾 Descargar mapa HTML",
                data=f,
                file_name=f"mapa_ruta_{uploaded_file.name.replace('.gpx', '')}.html",
                mime="text/html"
            )
    else:
        st.error("❌ No se pudo generar el mapa. Revisa el registro del análisis.")

else:
    st.warning("Por favor, sube un archivo `.gpx` para comenzar.")

st.markdown("---")
st.caption("Desarrollado con ❤️ usando Streamlit y Folium.")
