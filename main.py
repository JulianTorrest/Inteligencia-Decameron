import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import plotly.express as px
import plotly.graph_objects as go

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
        st.stop() # Stop execution if file cannot be downloaded
        return None
    except Exception as e:
        st.error(f"Error al leer el archivo Excel: {e}. Asegúrate de que es un archivo .xlsx válido.")
        st.stop() # Stop execution if file cannot be read
        return None

df = load_data(GITHUB_EXCEL_URL)

# Only proceed if df was loaded successfully
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

    st.markdown("---")

    st.header("4. Opciones de Respuesta para Variables Categóricas")
    st.write("Identificando columnas categóricas y sus valores únicos.")

    # Define a threshold for what we consider "categorical" based on unique values
    UNIQUE_VALUES_THRESHOLD = 50

    categorical_cols = []

    for col in df.columns:
        if df[col].dtype == 'object' or pd.api.types.is_categorical_dtype(df[col]):
            num_unique = df[col].nunique()
            if 1 < num_unique <= UNIQUE_VALUES_THRESHOLD:
                categorical_cols.append(col)
            elif num_unique <= 1:
                st.info(f"La columna '{col}' tiene {num_unique} valor(es) único(s) y no se considera categórica para este análisis.")
            else:
                st.info(f"La columna '{col}' es de tipo objeto pero tiene {num_unique} valores únicos (posiblemente texto libre o ID). No se muestra su listado de opciones aquí.")

    if not categorical_cols:
        st.warning("No se encontraron columnas categóricas basadas en los criterios definidos (tipo de dato 'object'/'category' y menos de 50 valores únicos).")
    else:
        st.write("Las siguientes columnas fueron identificadas como categóricas y sus opciones de respuesta son:")
        for col in categorical_cols:
            st.subheader(f"Columna: **{col}**")
            options = df[col].dropna().unique().tolist()
            options.sort()
            st.write(options)
            st.write(f"Número de opciones únicas: **{len(options)}**")

    st.markdown("---")

    st.header("5. Proceso de Limpieza de Datos Personalizado")
    st.write("A continuación, se muestra el proceso de limpieza aplicado, **excluyendo la columna 'Aerolinea' de la eliminación de vacíos**.")
    st.write("Se creará una copia del DataFrame para aplicar la limpieza.")

    df_cleaned = df.copy()

    # --- Cleaning Step 1: Handling Numerical NaNs ---
    st.subheader("Limpieza 5.1: Rellenar valores numéricos vacíos con 0")
    numeric_cols = df_cleaned.select_dtypes(include=['number']).columns
    df_cleaned[numeric_cols] = df_cleaned[numeric_cols].fillna(0)
    st.write("Se han rellenado los valores nulos en columnas numéricas con 0.")

    # --- Cleaning Step 2: Handling Categorical/Object NaNs (Excluding 'Aerolinea') ---
    st.subheader("Limpieza 5.2: Rellenar valores categóricos/objeto vacíos (excepto 'Aerolinea')")

    non_numeric_cols = df_cleaned.select_dtypes(exclude=['number']).columns
    cols_to_fill_non_numeric = [col for col in non_numeric_cols if col != "Aerolinea"]

    if cols_to_fill_non_numeric:
        df_cleaned[cols_to_fill_non_numeric] = df_cleaned[cols_to_fill_non_numeric].fillna('Desconocido')
        st.write(f"Columnas no numéricas rellenadas con 'Desconocido': {', '.join(cols_to_fill_non_numeric)}")
    else:
        st.info("No hay columnas no numéricas para rellenar (excluyendo 'Aerolinea').")

    # --- Cleaning Step 3: Standardize 'Plan' column ---
    st.subheader("Limpieza 5.3: Estandarización de la columna 'Plan'")
    # Creating a dictionary for mapping common typos to correct values
    plan_mapping = {
        'Solo Hotel + Carreteroo': 'Solo Hotel + Carretero',
        'Solo Hotell': 'Solo Hotel',
        'Solo Hotel + Vueloo': 'Solo Hotel + Vuelo'
    }
    df_cleaned['Plan'] = df_cleaned['Plan'].replace(plan_mapping)
    st.write("Se han estandarizado los valores en la columna 'Plan'.")
    st.write("Valores únicos de 'Plan' después de la estandarización:")
    st.write(df_cleaned['Plan'].unique().tolist())

    # --- Cleaning Step 4: Convert Date Columns ---
    st.subheader("Limpieza 5.4: Conversión de columnas de Fecha")
    try:
        df_cleaned['Fecha Facturacion'] = pd.to_datetime(df_cleaned['Fecha Facturacion'])
        df_cleaned['Fecha Check-in'] = pd.to_datetime(df_cleaned['Fecha Check-in'])
        st.write("Las columnas 'Fecha Facturacion' y 'Fecha Check-in' han sido convertidas a tipo fecha.")
    except Exception as e:
        st.warning(f"No se pudieron convertir las columnas de fecha. Error: {e}")

    # --- Cleaning Step 5: Verify NaNs after custom cleaning ---
    st.subheader("Limpieza 5.5: Verificación de valores vacíos después de la limpieza personalizada")
    final_missing_values = df_cleaned.isnull().sum()
    final_missing_values = final_missing_values[final_missing_values > 0]

    if final_missing_values.empty:
        st.info("¡No quedan valores vacíos en el DataFrame después de la limpieza personalizada!")
    else:
        st.dataframe(final_missing_values.rename("Valores Vacíos (Después de Limpieza Personalizada)"))
        st.write(f"Como se solicitó, la columna 'Aerolinea' aún puede contener vacíos si los tenía originalmente.")

    st.write("Primeras 5 filas del DataFrame después de la limpieza personalizada y preparación para gráficos:")
    st.dataframe(df_cleaned.head())


    st.markdown("---")
    st.header("6. Visualizaciones de Datos")
    st.write("Explora las relaciones y distribuciones de tus datos con estos gráficos interactivos.")

    # --- Gráfico 1: Ingreso Total por Destino (Bar Chart) ---
    st.subheader("6.1. Ingreso Total por Destino")
    fig1 = px.bar(
        df_cleaned.groupby('Destino')['Ingreso Total'].sum().reset_index(),
        x='Destino',
        y='Ingreso Total',
        title='Ingreso Total por Destino',
        labels={'Ingreso Total': 'Ingreso Total ($)', 'Destino': 'Destino'},
        color='Destino'
    )
    st.plotly_chart(fig1, use_container_width=True)
    st.write("Este gráfico de barras muestra la suma total de ingresos generados por cada destino.")

    # --- Gráfico 2: Número de Room Nights por Plan (Bar Chart) ---
    st.subheader("6.2. Número de Room Nights por Plan")
    fig2 = px.bar(
        df_cleaned.groupby('Plan')['# Room Nights'].sum().reset_index(),
        x='Plan',
        y='# Room Nights',
        title='Número de Room Nights por Plan',
        labels={'# Room Nights': 'Total Room Nights', 'Plan': 'Tipo de Plan'},
        color='Plan'
    )
    st.plotly_chart(fig2, use_container_width=True)
    st.write("Visualiza la cantidad total de noches de habitación vendidas para cada tipo de plan.")

    # --- Gráfico 3: Distribución de Clientes por Tipo de Cliente (Pie Chart) ---
    st.subheader("6.3. Distribución de Clientes por Tipo de Cliente")
    fig3 = px.pie(
        df_cleaned,
        names='Tipo Cliente',
        title='Distribución Porcentual de Clientes por Tipo',
        labels={'Tipo Cliente': 'Tipo de Cliente'}
    )
    st.plotly_chart(fig3, use_container_width=True)
    st.write("Este gráfico circular muestra la proporción de clientes en cada categoría (Agencia, Corporativo, Turista).")

    # --- Gráfico 4: Ingreso Total por Aerolínea (Bar Chart) ---
    st.subheader("6.4. Ingreso Total por Aerolínea")
    # Handling potential NaN in Aerolinea by converting to string for display if needed
    df_cleaned['Aerolinea_Display'] = df_cleaned['Aerolinea'].fillna('No Definido')
    fig4 = px.bar(
        df_cleaned.groupby('Aerolinea_Display')['Ingreso Total'].sum().reset_index(),
        x='Aerolinea_Display',
        y='Ingreso Total',
        title='Ingreso Total por Aerolínea',
        labels={'Ingreso Total': 'Ingreso Total ($)', 'Aerolinea_Display': 'Aerolínea'},
        color='Aerolinea_Display'
    )
    st.plotly_chart(fig4, use_container_width=True)
    st.write("Muestra la contribución de cada aerolínea al ingreso total. 'No Definido' incluye casos sin aerolínea.")

    # --- Gráfico 5: Valor Total por País (Bar Chart) ---
    st.subheader("6.5. Valor Total por País")
    fig5 = px.bar(
        df_cleaned.groupby('Pais')['Valor Total'].sum().reset_index(),
        x='Pais',
        y='Valor Total',
        title='Valor Total de Ventas por País',
        labels={'Valor Total': 'Valor Total ($)', 'Pais': 'País de Origen'},
        color='Pais'
    )
    st.plotly_chart(fig5, use_container_width=True)
    st.write("Compara el valor total de las ventas por el país de origen del cliente.")

    # --- Gráfico 6: Tendencia de Ingreso Total por Fecha de Facturación (Line Chart) ---
    st.subheader("6.6. Tendencia de Ingreso Total por Fecha de Facturación")
    # Resample by month for cleaner trend
    df_monthly_revenue = df_cleaned.set_index('Fecha Facturacion')['Ingreso Total'].resample('M').sum().reset_index()
    fig6 = px.line(
        df_monthly_revenue,
        x='Fecha Facturacion',
        y='Ingreso Total',
        title='Tendencia Mensual de Ingreso Total',
        labels={'Fecha Facturacion': 'Fecha', 'Ingreso Total': 'Ingreso Total ($)'},
        markers=True
    )
    st.plotly_chart(fig6, use_container_width=True)
    st.write("Este gráfico de línea muestra cómo han evolucionado los ingresos totales mes a mes.")

    # --- Gráfico 7: Relación entre # Room Nights e Ingreso Total (Scatter Plot) ---
    st.subheader("6.7. Relación entre Room Nights e Ingreso Total")
    fig7 = px.scatter(
        df_cleaned,
        x='# Room Nights',
        y='Ingreso Total',
        title='Relación entre Noches de Habitación e Ingreso Total',
        labels={'# Room Nights': 'Número de Noches de Habitación', 'Ingreso Total': 'Ingreso Total ($)'},
        hover_name='ID Cliente' # Show client ID on hover
    )
    st.plotly_chart(fig7, use_container_width=True)
    st.write("Un gráfico de dispersión para ver la correlación entre las noches de habitación y el ingreso generado.")

    # --- Gráfico 8: Destino vs. Tipo de Cliente (Heatmap/Crosstab) ---
    st.subheader("6.8. Conteo de Clientes por Destino y Tipo de Cliente")
    crosstab_df = pd.crosstab(df_cleaned['Destino'], df_cleaned['Tipo Cliente'])
    fig8 = px.imshow(
        crosstab_df,
        text_auto=True, # Show values on heatmap
        title='Conteo de Clientes por Destino y Tipo de Cliente',
        labels={'x': 'Tipo de Cliente', 'y': 'Destino', 'color': 'Conteo'}
    )
    st.plotly_chart(fig8, use_container_width=True)
    st.write("Un mapa de calor que muestra la cantidad de clientes de cada tipo visitando cada destino.")

    # --- Gráfico 9: # Room Nights promedio por Tipo de Cliente (Bar Chart) ---
    st.subheader("6.9. Promedio de Room Nights por Tipo de Cliente")
    fig9 = px.bar(
        df_cleaned.groupby('Tipo Cliente')['# Room Nights'].mean().reset_index(),
        x='Tipo Cliente',
        y='# Room Nights',
        title='Promedio de Noches de Habitación por Tipo de Cliente',
        labels={'# Room Nights': 'Promedio de Noches de Habitación', 'Tipo Cliente': 'Tipo de Cliente'},
        color='Tipo Cliente'
    )
    st.plotly_chart(fig9, use_container_width=True)
    st.write("Este gráfico compara el promedio de noches que reserva cada tipo de cliente.")

    # --- Gráfico 10: Distribución de Valor Total (Histogram) ---
    st.subheader("6.10. Distribución del Valor Total")
    fig10 = px.histogram(
        df_cleaned,
        x='Valor Total',
        nbins=50, # Number of bins for the histogram
        title='Distribución del Valor Total de las Reservas',
        labels={'Valor Total': 'Valor Total ($)'}
    )
    st.plotly_chart(fig10, use_container_width=True)
    st.write("Un histograma para ver la distribución de los valores totales de las transacciones. Ayuda a identificar el rango de precios más común.")

    # --- Gráfico 11: Ingreso Total por País y Tipo de Cliente (Grouped Bar Chart) ---
    st.subheader("6.11. Ingreso Total por País y Tipo de Cliente")
    fig11 = px.bar(
        df_cleaned.groupby(['Pais', 'Tipo Cliente'])['Ingreso Total'].sum().reset_index(),
        x='Pais',
        y='Ingreso Total',
        color='Tipo Cliente',
        barmode='group', # Grouped bars
        title='Ingreso Total por País y Tipo de Cliente',
        labels={'Ingreso Total': 'Ingreso Total ($)', 'Pais': 'País', 'Tipo Cliente': 'Tipo de Cliente'}
    )
    st.plotly_chart(fig11, use_container_width=True)
    st.write("Compara los ingresos generados por cada tipo de cliente en cada país.")

    # --- Gráfico 12: # Room Nights por Destino y Tipo de Cliente (Grouped Bar Chart) ---
    st.subheader("6.12. Room Nights por Destino y Tipo de Cliente")
    fig12 = px.bar(
        df_cleaned.groupby(['Destino', 'Tipo Cliente'])['# Room Nights'].sum().reset_index(),
        x='Destino',
        y='# Room Nights',
        color='Tipo Cliente',
        barmode='group',
        title='Room Nights por Destino y Tipo de Cliente',
        labels={'# Room Nights': 'Total Room Nights', 'Destino': 'Destino', 'Tipo Cliente': 'Tipo de Cliente'}
    )
    st.plotly_chart(fig12, use_container_width=True)
    st.write("Analiza cómo se distribuyen las noches de habitación entre destinos y tipos de cliente.")

    # --- Gráfico 13: Box Plot de Valor Total por Tipo de Cliente ---
    st.subheader("6.13. Distribución del Valor Total por Tipo de Cliente (Box Plot)")
    fig13 = px.box(
        df_cleaned,
        x='Tipo Cliente',
        y='Valor Total',
        title='Distribución del Valor Total por Tipo de Cliente',
        labels={'Tipo Cliente': 'Tipo de Cliente', 'Valor Total': 'Valor Total ($)'},
        color='Tipo Cliente'
    )
    st.plotly_chart(fig13, use_container_width=True)
    st.write("Un diagrama de caja para ver la distribución, mediana y posibles valores atípicos del valor total de las ventas para cada tipo de cliente.")

    # --- Gráfico 14: # Room Nights vs. Fecha Check-in (Line chart - Daily) ---
    st.subheader("6.14. # Room Nights por Fecha de Check-in")
    df_checkin_nights = df_cleaned.groupby('Fecha Check-in')['# Room Nights'].sum().reset_index()
    fig14 = px.line(
        df_checkin_nights,
        x='Fecha Check-in',
        y='# Room Nights',
        title='Total de Room Nights por Fecha de Check-in',
        labels={'Fecha Check-in': 'Fecha de Check-in', '# Room Nights': 'Total Room Nights'},
        markers=True
    )
    st.plotly_chart(fig14, use_container_width=True)
    st.write("Muestra la tendencia diaria o semanal de las noches de habitación, útil para identificar temporadas altas y bajas.")

    # --- Gráfico 15: Ingreso Total por Plan y Aerolinea (Faceting / Stacked Bar) ---
    st.subheader("6.15. Ingreso Total por Plan y Aerolínea")
    # Use Aerolinea_Display to include 'No Definido' in the plot
    fig15 = px.bar(
        df_cleaned.groupby(['Plan', 'Aerolinea_Display'])['Ingreso Total'].sum().reset_index(),
        x='Plan',
        y='Ingreso Total',
        color='Aerolinea_Display',
        title='Ingreso Total por Plan Desglosado por Aerolínea',
        labels={'Ingreso Total': 'Ingreso Total ($)', 'Plan': 'Tipo de Plan', 'Aerolinea_Display': 'Aerolínea'}
    )
    st.plotly_chart(fig15, use_container_width=True)
    st.write("Analiza qué aerolíneas contribuyen a los ingresos para cada tipo de plan. Las barras apiladas muestran la contribución de cada aerolínea dentro de cada plan.")

    st.markdown(
        """
        ---
        **Próximos Pasos Sugeridos:**
        * **Análisis Temporal Detallado:** Podríamos extraer el mes, día de la semana o trimestre de las fechas para análisis más granular.
        * **Correlaciones:** Investigar las correlaciones entre variables numéricas para entender mejor su relación.
        * **Segmentación:** Utilizar estas visualizaciones para segmentar a tus clientes o destinos y crear estrategias más específicas.
        """
    )
