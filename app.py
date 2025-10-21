import streamlit as st
import tempfile
import io
import contextlib
from pathlib import Path
from analizar_superficie_con_mapa import main
import imgkit
from PIL import Image

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
generando un mapa estático con estadísticas de superficie.
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

    # Buscar el HTML generado
    map_filename = f"mapa_ruta_v9_{tmp_path.stem}.html"
    map_path = Path.cwd() / map_filename

    if map_path.exists():
        st.info("Generando imagen del mapa...")

        # Generar imagen PNG a partir del HTML
        img_output_path = Path.cwd() / f"{tmp_path.stem}_map.png"
        try:
            imgkit.from_file(str(map_path), str(img_output_path))
            image = Image.open(img_output_path)
            st.image(image, caption="Mapa generado", use_column_width=True)

            # Descargar imagen
            with open(img_output_path, "rb") as f:
                st.download_button(
                    label="💾 Descargar imagen PNG",
                    data=f,
                    file_name=f"{tmp_path.stem}_map.png",
                    mime="image/png"
                )
        except Exception as e:
            st.error(f"No se pudo generar la imagen del mapa: {e}")

    else:
        st.error("❌ No se pudo generar el mapa. Revisa el registro del análisis.")

else:
    st.warning("Por favor, sube un archivo `.gpx` para comenzar.")

st.markdown("---")
st.caption("Desarrollado con ❤️ usando Streamlit, Folium e imgkit.")
