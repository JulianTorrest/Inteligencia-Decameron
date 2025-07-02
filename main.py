import streamlit as st
import pandas as pd
import requests
from io import BytesIO

# --- Configuration ---
# The raw GitHub URL for your Excel file
GITHUB_EXCEL_URL = "https://raw.githubusercontent.com/JulianTorrest/Inteligencia-Decameron/main/datos_hotel_final.xlsx"

# --- Streamlit App ---
st.set_page_config(layout="wide")
st.title("Análisis de Datos de Hotel desde GitHub")

st.write(f"Cargando archivo desde: [{GITHUB_EXCEL_URL}]({GITHUB_EXCEL_URL})")

@st.cache_data # Cache the data to avoid re-downloading on every rerun
def load_data(url):
    """Loads the Excel file from a given URL into a pandas DataFrame."""
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
        df = pd.read_excel(BytesIO(response.content))
        return df
    except requests.exceptions.RequestException as e:
        st.error(f"Error al descargar el archivo: {e}. Por favor, verifica la URL.")
        return None
    except Exception as e:
        st.error(f"Error al leer el archivo Excel: {e}. Asegúrate de que es un archivo .xlsx válido.")
        return None

df = load_data(GITHUB_EXCEL_URL)

if df is not None:
    st.header("1. Previsualización de los Datos")
    st.write("Las primeras 5 filas del DataFrame:")
    st.dataframe(df.head())
    st.write(f"El DataFrame tiene {df.shape[0]} filas y {df.shape[1]} columnas.")

    st.header("2. Listado de Columnas")
    st.write("Columnas disponibles en el DataFrame:")
    st.write(df.columns.tolist())

    st.header("3. Identificación de Valores Vacíos (NaNs)")
    st.write("Conteo de valores vacíos por columna:")
    # Calculate the sum of null values for each column
    missing_values = df.isnull().sum()
    # Filter to show only columns with missing values
    missing_values = missing_values[missing_values > 0]

    if missing_values.empty:
        st.info("¡No se encontraron valores vacíos en el DataFrame!")
    else:
        st.dataframe(missing_values.rename("Valores Vacíos"))
        st.write("Columnas con valores vacíos:")
        st.write(missing_values.index.tolist())

    st.header("4. Proceso Básico de Limpieza de Datos")
    st.write("A continuación, se muestra un ejemplo básico de limpieza de datos.")
    st.write("Se creará una copia del DataFrame para aplicar la limpieza.")

    df_cleaned = df.copy()

    # Example 1: Dropping rows with any missing values
    st.subheader("Limpieza 1: Eliminar filas con valores vacíos")
    rows_before_drop = df_cleaned.shape[0]
    df_cleaned_dropped = df_cleaned.dropna()
    rows_after_drop = df_cleaned_dropped.shape[0]
    st.write(f"Filas antes de eliminar: {rows_before_drop}")
    st.write(f"Filas después de eliminar: {rows_after_drop}")
    st.write(f"Se eliminaron {rows_before_drop - rows_after_drop} filas con valores vacíos.")
    st.dataframe(df_cleaned_dropped.head())

    # Example 2: Filling missing values (e.g., with 0, mean, or a specific string)
    st.subheader("Limpieza 2: Rellenar valores vacíos")
    st.write("Para este ejemplo, rellenaremos los valores numéricos vacíos con 0 y los no numéricos con 'Desconocido'.")

    # Fill numerical NaNs with 0
    numeric_cols = df_cleaned.select_dtypes(include=['number']).columns
    df_cleaned[numeric_cols] = df_cleaned[numeric_cols].fillna(0)

    # Fill non-numerical NaNs with 'Desconocido'
    non_numeric_cols = df_cleaned.select_dtypes(exclude=['number']).columns
    df_cleaned[non_numeric_cols] = df_cleaned[non_numeric_cols].fillna('Desconocido')

    st.write("Conteo de valores vacíos después de rellenar:")
    st.dataframe(df_cleaned.isnull().sum().rename("Valores Vacíos (Después de Rellenar)"))
    st.write("Primeras 5 filas del DataFrame después de rellenar:")
    st.dataframe(df_cleaned.head())

    st.markdown(
        """
        ---
        **Nota sobre la limpieza:**
        El proceso de limpieza exacto dependerá de la naturaleza de tus datos y del análisis que desees realizar.
        Algunas opciones comunes incluyen:
        - **Eliminar filas/columnas:** Si la cantidad de valores vacíos es pequeña o la columna no es crítica. (`df.dropna()`)
        - **Imputación:** Rellenar valores vacíos con la media, mediana, moda, un valor específico o usar métodos más avanzados. (`df.fillna()`)
        - **Transformación de datos:** Convertir tipos de datos, estandarizar formatos, etc.

        Para ejecutar esta aplicación en Streamlit Cloud, guarda el código en un archivo `nombre_app.py`
        y asegúrate de tener `pandas` y `requests` en tu archivo `requirements.txt`.
        """
    )
