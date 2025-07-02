import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import plotly.express as px
import plotly.graph_objects as go
import numpy as np # For numerical operations, especially with NaN

# --- Configuration ---
# The raw GitHub URL for your Excel file
GITHUB_EXCEL_URL = "https://raw.githubusercontent.com/JulianTorrest/Inteligencia-Decameron/main/datos_hotel_final.xlsx"

# Commission Table provided by the user
COMMISSION_RATES = {
    'Colombia': {'AV': 0.08, 'LA': 0.07, 'CM': 0.06},
    'México': {'AV': 0.10, 'LA': 0.09, 'CM': 0.08},
    'Ecuador': {'AV': 0.07, 'LA': 0.06, 'CM': 0.05},
    'Perú': {'AV': 0.09, 'LA': 0.08, 'CM': 0.07}
}

# Mock FX US$ rates (as it's a separate sheet, we'll simulate it)
# In a real scenario, you'd load this from the Excel file if it's a second sheet
FX_RATES_DATA = {
    'Año': [2023, 2023, 2023, 2023, 2024, 2024, 2024, 2024, 2024, 2024, 2024, 2024, 2024, 2024, 2024, 2024],
    'Mes': [1, 2, 3, 4, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], # Assuming 1-12 for months
    'Colombia_FX': [3800, 3900, 3850, 4000, 3950, 4050, 4020, 3980, 4100, 4080, 4120, 4150, 4200, 4250, 4300, 4350],
    'México_FX': [19.5, 20.0, 19.8, 20.5, 20.2, 20.8, 20.5, 20.3, 21.0, 20.9, 21.1, 21.3, 21.5, 21.8, 22.0, 22.2]
}
FX_DF = pd.DataFrame(FX_RATES_DATA)


# --- Streamlit App ---
st.set_page_config(layout="wide")
st.title("Plataforma de Análisis de Datos de Hotel")

st.markdown("---")
st.sidebar.header("Navegación")
section = st.sidebar.radio("Ir a la Sección:",
                           ["1. EDA",
                            "2. Transformación y Análisis de Datos",
                            "3. Dashboard Ejecutivo"])

# --- Data Loading and Initial Preparation (Common to all sections) ---
st.write(f"Cargando archivo desde: [{GITHUB_EXCEL_URL}]({GITHUB_EXCEL_URL})")

@st.cache_data # Cache the data to avoid re-downloading on every rerun
def load_and_prepare_data(url, fx_df_param):
    """
    Loads the Excel file, performs initial cleaning, preparation,
    and applies transformations common to all analysis sections.
    """
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
        df = pd.read_excel(BytesIO(response.content))

        # --- Initial Cleaning and Type Conversion ---
        # 1. Fill numerical NaNs with 0 (for analysis, can be adjusted)
        numeric_cols = df.select_dtypes(include=['number']).columns
        df[numeric_cols] = df[numeric_cols].fillna(0)

        # 2. Fill non-numerical NaNs with 'Desconocido' (excluding 'Aerolinea')
        non_numeric_cols = df.select_dtypes(exclude=['number']).columns
        cols_to_fill_non_numeric = [col for col in non_numeric_cols if col != "Aerolinea"]
        if cols_to_fill_non_numeric:
            df[cols_to_fill_non_numeric] = df[cols_to_fill_non_numeric].fillna('Desconocido')

        # 3. Standardize 'Plan' column
        plan_mapping = {
            'Solo Hotel + Carreteroo': 'Solo Hotel + Carretero',
            'Solo Hotell': 'Solo Hotel',
            'Solo Hotel + Vueloo': 'Solo Hotel + Vuelo'
        }
        df['Plan'] = df['Plan'].replace(plan_mapping)
        
        # 4. Convert Date Columns
        for date_col in ['Fecha Facturacion', 'Fecha Check-in']:
            if date_col in df.columns:
                df[date_col] = pd.to_datetime(df[date_col], errors='coerce') # coerce will turn invalid dates into NaT
        
        # Add 'Year' and 'Month' columns for temporal analysis
        df['Año Facturacion'] = df['Fecha Facturacion'].dt.year.fillna(0).astype(int)
        df['Mes Facturacion'] = df['Fecha Facturacion'].dt.month.fillna(0).astype(int)
        df['Mes Nombre Facturacion'] = df['Fecha Facturacion'].dt.strftime('%B').fillna('Desconocido') # Full month name

        # Create 'Aerolinea_Display' for plotting if 'Aerolinea' has NaNs
        df['Aerolinea_Display'] = df['Aerolinea'].fillna('No Definido')

        # --- Apply specific transformations for all sections to have clean, enhanced data ---
        # A. Clasificación de mercado
        df['Mercado'] = df.apply(
            lambda row: "Local" if row['Pais'] == row['Destino'] else "Emisivo",
            axis=1
        )

        # B. Conversión de ingresos a dólares
        df = pd.merge(
            df,
            fx_df_param,
            left_on=['Año Facturacion', 'Mes Facturacion'],
            right_on=['Año', 'Mes'],
            how='left'
        )
        def calculate_local_currency_income(row):
            if row['Pais'] == 'Colombia':
                return row['Ingreso Total'] * row['Colombia_FX'] if pd.notna(row['Colombia_FX']) else np.nan
            elif row['Pais'] == 'México':
                return row['Ingreso Total'] * row['México_FX'] if pd.notna(row['México_FX']) else np.nan
            else: # For other countries, assume Ingreso Total is already local currency or cannot convert
                return np.nan
        df['Ingreso Moneda Local'] = df.apply(calculate_local_currency_income, axis=1)

        # C. Tratamiento de valores faltantes para "Vuelo" en el plan y aerolínea vacía
        df['Aerolinea'] = df['Aerolinea'].astype(str) # Convert to string to avoid issues with NaN during contains()
        vuelo_plans = ['Solo Hotel + Vuelo']
        mask_vuelo_no_aerolinea = (df['Plan'].isin(vuelo_plans)) & (df['Aerolinea'] == 'nan')
        if mask_vuelo_no_aerolinea.any():
            for index, row in df[mask_vuelo_no_aerolinea].iterrows():
                destination = row['Destino']
                most_frequent_airline = df[
                    (df['Destino'] == destination) & (df['Aerolinea'] != 'nan')
                ]['Aerolinea'].mode()
                if not most_frequent_airline.empty:
                    df.loc[index, 'Aerolinea'] = most_frequent_airline.iloc[0]
                else:
                    df.loc[index, 'Aerolinea'] = 'Vuelo No Especificado'
        df['Aerolinea'] = df['Aerolinea'].replace('nan', np.nan) # Convert 'nan' string back to actual NaN
        df['Aerolinea_Display'] = df['Aerolinea'].fillna('No Definido') # Re-generate Aerolinea_Display after imputation

        # D. Cálculo de comisión por aerolínea y destino
        def calculate_commission(row):
            destino = row['Destino']
            aerolinea = row['Aerolinea_Display'] # Use Aerolinea_Display as it handles 'No Definido'
            ingreso = row['Ingreso Total']

            # Map 'No Definido' to a key not in COMMISSION_RATES or handle specifically
            actual_aerolinea_key = row['Aerolinea'] if pd.notna(row['Aerolinea']) else None

            if pd.notna(destino) and actual_aerolinea_key in ['AV', 'LA', 'CM'] and destino in COMMISSION_RATES and actual_aerolinea_key in COMMISSION_RATES[destino]:
                return ingreso * COMMISSION_RATES[destino][actual_aerolinea_key]
            return 0 # No commission if data is missing or not found in table

        df['Comision'] = df.apply(calculate_commission, axis=1)

        # E. Distribución de presupuesto de facturación 2025 (Bonus Opcional)
        # This part calculates total_sales_2024 and estimated_monthly_budget_2025
        # and stores it in session state so it can be used across sections without recalculating on every widget interaction
        sales_2024 = df[df['Año Facturacion'] == 2024]['Ingreso Total'].sum()
        if sales_2024 > 0:
            budget_2025_estimated = sales_2024 * 1.30
            monthly_sales_2024 = df[df['Año Facturacion'] == 2024].groupby('Mes Facturacion')['Ingreso Total'].sum()
            total_sales_2024_for_dist = monthly_sales_2024.sum()
            if total_sales_2024_for_dist > 0:
                monthly_distribution_ratio = monthly_sales_2024 / total_sales_2024_for_dist
                estimated_monthly_budget_2025 = monthly_distribution_ratio * budget_2025_estimated
                st.session_state['estimated_monthly_budget_2025'] = estimated_monthly_budget_2025.reindex(range(1, 13), fill_value=0).values
                st.session_state['budget_2025_total'] = budget_2025_estimated
            else:
                st.session_state['estimated_monthly_budget_2025'] = np.zeros(12)
                st.session_state['budget_2025_total'] = 0
        else:
            st.session_state['estimated_monthly_budget_2025'] = np.zeros(12)
            st.session_state['budget_2025_total'] = 0

        return df

    except requests.exceptions.RequestException as e:
        st.error(f"Error al descargar el archivo: {e}. Por favor, verifica la URL.")
        st.stop()
    except Exception as e:
        st.error(f"Error al leer o preparar el archivo Excel: {e}. Asegúrate de que es un archivo .xlsx válido y el formato de datos es correcto.")
        st.stop()

# Load and prepare data once, passing FX_DF
df_transformed = load_and_prepare_data(GITHUB_EXCEL_URL, FX_DF)

# --- SECTION: 1. EDA ---
if section == "1. EDA":
    st.header("1. Exploratory Data Analysis (EDA)")
    st.write("Esta sección presenta una visión general inicial de los datos, las columnas y los valores faltantes, así como visualizaciones clave para entender la distribución y relaciones.")

    st.subheader("1.1. Previsualización de los Datos")
    st.write("Las primeras 5 filas del DataFrame (después de la preparación inicial):")
    st.dataframe(df_transformed.head())
    st.write(f"El DataFrame tiene {df_transformed.shape[0]} filas y {df_transformed.shape[1]} columnas.")

    st.subheader("1.2. Listado de Columnas")
    st.write("Columnas disponibles en el DataFrame:")
    st.write(df_transformed.columns.tolist())

    st.subheader("1.3. Identificación de Valores Vacíos (NaNs)")
    st.write("Conteo de valores vacíos por columna (después de la limpieza inicial y transformaciones):")
    missing_values = df_transformed.isnull().sum()
    missing_values = missing_values[missing_values > 0]

    if missing_values.empty:
        st.info("¡No se encontraron valores vacíos en el DataFrame después de la limpieza y transformaciones!")
    else:
        st.dataframe(missing_values.rename("Valores Vacíos"))
        st.write("Columnas con valores vacíos (solo 'Ingreso Moneda Local' si aplica para otros países):")
        st.write(missing_values.index.tolist())

    st.subheader("1.4. Opciones de Respuesta para Variables Categóricas")
    st.write("Identificando columnas categóricas y sus valores únicos.")
    UNIQUE_VALUES_THRESHOLD = 50
    categorical_cols = []

    for col in df_transformed.columns:
        if df_transformed[col].dtype == 'object' or pd.api.types.is_categorical_dtype(df_transformed[col]):
            num_unique = df_transformed[col].nunique()
            if 1 < num_unique <= UNIQUE_VALUES_THRESHOLD:
                categorical_cols.append(col)
            elif num_unique <= 1:
                st.info(f"La columna '{col}' tiene {num_unique} valor(es) único(s) y no se considera categórica para este análisis.")
            else:
                st.info(f"La columna '{col}' es de tipo objeto pero tiene {num_unique} valores únicos (posiblemente texto libre o ID). No se muestra su listado de opciones aquí.")

    if not categorical_cols:
        st.warning("No se encontraron columnas categóricas basadas en los criterios definidos.")
    else:
        st.write("Las siguientes columnas fueron identificadas como categóricas y sus opciones de respuesta son:")
        for col in categorical_cols:
            st.markdown(f"**Columna: {col}**")
            options = df_transformed[col].dropna().unique().tolist()
            options.sort()
            st.write(options)
            st.write(f"Número de opciones únicas: **{len(options)}**")

    st.markdown("---")
    st.subheader("1.5. Visualizaciones de Datos (EDA)")
    st.write("Explora las relaciones y distribuciones de tus datos con estos gráficos interactivos.")

    # List of EDA plots (keeping them concise here as they were detailed before)
    # The plots use df_transformed now that it includes all transformations
    plots_to_display = [
        ("Ingreso Total por Destino", px.bar(df_transformed.groupby('Destino')['Ingreso Total'].sum().reset_index(), x='Destino', y='Ingreso Total', title='Ingreso Total por Destino', color='Destino')),
        ("Número de Room Nights por Plan", px.bar(df_transformed.groupby('Plan')['# Room Nights'].sum().reset_index(), x='Plan', y='# Room Nights', title='Número de Room Nights por Plan', color='Plan')),
        ("Distribución de Clientes por Tipo de Cliente", px.pie(df_transformed, names='Tipo Cliente', title='Distribución Porcentual de Clientes por Tipo')),
        ("Ingreso Total por Aerolínea", px.bar(df_transformed.groupby('Aerolinea_Display')['Ingreso Total'].sum().reset_index(), x='Aerolinea_Display', y='Ingreso Total', title='Ingreso Total por Aerolínea', color='Aerolinea_Display')),
        ("Valor Total por País", px.bar(df_transformed.groupby('Pais')['Valor Total'].sum().reset_index(), x='Pais', y='Valor Total', title='Valor Total de Ventas por País', color='Pais')),
        ("Tendencia Mensual de Ingreso Total por Fecha de Facturación", px.line(df_transformed.set_index('Fecha Facturacion')['Ingreso Total'].resample('M').sum().reset_index(), x='Fecha Facturacion', y='Ingreso Total', title='Tendencia Mensual de Ingreso Total', markers=True)),
        ("Relación entre Room Nights e Ingreso Total", px.scatter(df_transformed, x='# Room Nights', y='Ingreso Total', title='Relación entre Noches de Habitación e Ingreso Total', hover_name='ID Cliente')),
        ("Conteo de Clientes por Destino y Tipo de Cliente", px.imshow(pd.crosstab(df_transformed['Destino'], df_transformed['Tipo Cliente']), text_auto=True, title='Conteo de Clientes por Destino y Tipo de Cliente')),
        ("Promedio de Room Nights por Tipo de Cliente", px.bar(df_transformed.groupby('Tipo Cliente')['# Room Nights'].mean().reset_index(), x='Tipo Cliente', y='# Room Nights', title='Promedio de Noches de Habitación por Tipo de Cliente', color='Tipo Cliente')),
        ("Distribución del Valor Total", px.histogram(df_transformed, x='Valor Total', nbins=50, title='Distribución del Valor Total de las Reservas')),
        ("Ingreso Total por País y Tipo de Cliente", px.bar(df_transformed.groupby(['Pais', 'Tipo Cliente'])['Ingreso Total'].sum().reset_index(), x='Pais', y='Ingreso Total', color='Tipo Cliente', barmode='group', title='Ingreso Total por País y Tipo de Cliente')),
        ("Room Nights por Destino y Tipo de Cliente", px.bar(df_transformed.groupby(['Destino', 'Tipo Cliente'])['# Room Nights'].sum().reset_index(), x='Destino', y='# Room Nights', color='Tipo Cliente', barmode='group', title='Room Nights por Destino y Tipo de Cliente')),
        ("Distribución del Valor Total por Tipo de Cliente (Box Plot)", px.box(df_transformed, x='Tipo Cliente', y='Valor Total', title='Distribución del Valor Total por Tipo de Cliente', color='Tipo Cliente')),
        ("Room Nights por Fecha de Check-in", px.line(df_transformed.groupby('Fecha Check-in')['# Room Nights'].sum().reset_index(), x='Fecha Check-in', y='# Room Nights', title='Total de Room Nights por Fecha de Check-in', markers=True)),
        ("Ingreso Total por Plan y Aerolínea", px.bar(df_transformed.groupby(['Plan', 'Aerolinea_Display'])['Ingreso Total'].sum().reset_index(), x='Plan', y='Ingreso Total', color='Aerolinea_Display', title='Ingreso Total por Plan Desglosado por Aerolínea'))
    ]

    for title, fig in plots_to_display:
        st.markdown(f"#### {title}")
        st.plotly_chart(fig, use_container_width=True)


# --- SECTION: 2. TRANSFORMACIÓN Y ANÁLISIS DE DATOS ---
elif section == "2. Transformación y Análisis de Datos":
    st.header("2. Transformación y Análisis de Datos")
    st.write("Esta sección implementa transformaciones específicas y responde a preguntas de negocio.")
    st.write("El DataFrame ya ha sido cargado y preprocesado con todas las transformaciones necesarias para consistencia en la aplicación.")

    st.subheader("A. Clasificación de Mercado")
    st.write("La columna 'Mercado' ha sido agregada, indicando si el cliente es 'Local' (País == Destino) o 'Emisivo' (País != Destino).")
    st.dataframe(df_transformed[['Pais', 'Destino', 'Mercado']].head())
    market_distribution = df_transformed['Mercado'].value_counts().reset_index()
    market_distribution.columns = ['Mercado', 'Conteo']
    fig_market = px.bar(market_distribution, x='Mercado', y='Conteo', title='Distribución por Tipo de Mercado')
    st.plotly_chart(fig_market, use_container_width=True)

    st.subheader("B. Conversión de Ingresos a Moneda Local")
    st.write("Se ha agregado la columna 'Ingreso Moneda Local' aplicando tasas de cambio para México y Colombia. Para otros países, el valor es `NaN` o no se convierte.")
    st.dataframe(df_transformed[['Fecha Facturacion', 'Pais', 'Ingreso Total', 'Ingreso Moneda Local']].head())
    st.info("Nota: Las tasas de cambio se simulan en el código y se aplican a los `Ingreso Total` para obtener `Ingreso Moneda Local`.")

    st.subheader("C. Tratamiento de Valores Faltantes (Aerolinea en Plan 'Vuelo')")
    st.write("Para registros con 'Vuelo' en el plan y aerolínea vacía, se ha rellenado la `Aerolinea` con la aerolínea más frecuente para ese `Destino`. Si no se encontró, se usa 'Vuelo No Especificado'.")
    st.write(f"Conteo de valores vacíos en 'Aerolinea' después de la imputación para planes de Vuelo: **{df_transformed['Aerolinea'].isnull().sum()}**")
    st.dataframe(df_transformed[df_transformed['Plan'] == 'Solo Hotel + Vuelo'][['Plan', 'Aerolinea_Display', 'Destino', 'Pais']].head())


    st.subheader("D. Cálculo de Comisión por Aerolínea y Destino")
    st.write("Se ha agregado la columna 'Comision' calculada según la tabla de comisiones proporcionada.")
    st.dataframe(df_transformed[['Destino', 'Aerolinea_Display', 'Ingreso Total', 'Comision']].head())
    st.write(f"Comisión total calculada: **${df_transformed['Comision'].sum():,.2f}**")

    st.subheader("E. Distribución de Presupuesto de Facturación 2025 (Bonus Opcional)")
    if 'budget_2025_total' in st.session_state and st.session_state['budget_2025_total'] > 0:
        sales_2024 = df_transformed[df_transformed['Año Facturacion'] == 2024]['Ingreso Total'].sum()
        budget_2025_estimated = st.session_state['budget_2025_total']
        estimated_monthly_budget_2025 = st.session_state['estimated_monthly_budget_2025']

        st.write(f"Ingreso Total en 2024: **${sales_2024:,.2f}**")
        st.write(f"Presupuesto estimado para 2025 (30% mayor que 2024): **${budget_2025_estimated:,.2f}**")

        budget_df = pd.DataFrame({
            'Mes': [
                'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
            ],
            'Presupuesto Estimado 2025 ($)': estimated_monthly_budget_2025
        })
        st.dataframe(budget_df)
        fig_budget = px.bar(
            budget_df, x='Mes', y='Presupuesto Estimado 2025 ($)',
            title='Distribución Mensual Estimada del Presupuesto 2025'
        )
        st.plotly_chart(fig_budget, use_container_width=True)
    else:
        st.warning("No se puede calcular el presupuesto 2025, ya que no hay ingresos registrados para 2024 o el cálculo falló.")


# --- SECTION: 3. DASHBOARD EJECUTIVO (Streamlit) ---
elif section == "3. Dashboard Ejecutivo":
    st.header("3. Dashboard Ejecutivo")
    st.write("Este dashboard interactivo proporciona una visión ejecutiva de las métricas clave del hotel.")

    st.markdown("---")
    st.subheader("Filtros Interactivos")

    # Interactive Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        selected_years = st.multiselect(
            "Selecciona Año(s):",
            options=sorted(df_transformed['Año Facturacion'].unique().tolist()),
            default=sorted(df_transformed['Año Facturacion'].unique().tolist())
        )

    with col2:
        selected_client_types = st.multiselect(
            "Selecciona Tipo(s) de Cliente:",
            options=sorted(df_transformed['Tipo Cliente'].unique().tolist()),
            default=sorted(df_transformed['Tipo Cliente'].unique().tolist())
        )
    with col3:
        selected_countries = st.multiselect(
            "Selecciona País(es):",
            options=sorted(df_transformed['Pais'].unique().tolist()),
            default=sorted(df_transformed['Pais'].unique().tolist())
        )

    # Apply filters to a temporary dataframe for dashboard use
    df_filtered = df_transformed[
        (df_transformed['Año Facturacion'].isin(selected_years)) &
        (df_transformed['Tipo Cliente'].isin(selected_client_types)) &
        (df_transformed['Pais'].isin(selected_countries))
    ]

    if df_filtered.empty:
        st.warning("No hay datos que coincidan con los filtros seleccionados. Por favor, ajusta los filtros.")
    else:
        st.markdown("---")
        st.subheader("Visualizaciones del Dashboard")

        # --- Dashboard Viz 1: Ventas e ingresos por año (2024 y estimado 2025) ---
        st.markdown("##### 3.1. Ventas e Ingresos por Año (2024 y Estimado 2025)")
        # Get actual 2024 sales from filtered data
        actual_sales_2024_filtered = df_filtered[df_filtered['Año Facturacion'] == 2024]['Ingreso Total'].sum()

        # Prepare data for plotting
        years_data = {
            'Año': [],
            'Tipo': [],
            'Ingreso Total ($)': []
        }

        # Add 2024 actual sales
        if 2024 in selected_years:
            years_data['Año'].append(2024)
            years_data['Tipo'].append('Ingreso Real')
            years_data['Ingreso Total ($)'].append(actual_sales_2024_filtered)

        # Add 2025 estimated budget (if available in session_state)
        if 2025 in selected_years and 'budget_2025_total' in st.session_state:
            years_data['Año'].append(2025)
            years_data['Tipo'].append('Presupuesto Estimado')
            years_data['Ingreso Total ($)'].append(st.session_state['budget_2025_total'])

        df_annual_summary = pd.DataFrame(years_data)

        if not df_annual_summary.empty:
            fig_annual_sales = px.bar(
                df_annual_summary,
                x='Año',
                y='Ingreso Total ($)',
                color='Tipo',
                barmode='group',
                title='Ingresos Anuales (Real 2024 vs. Presupuesto Estimado 2025)',
                labels={'Ingreso Total ($)': 'Ingreso ($)'}
            )
            st.plotly_chart(fig_annual_sales, use_container_width=True)
        else:
            st.info("No hay datos de ingresos disponibles para los años seleccionados.")


        # --- Dashboard Viz 2: Distribución por tipo de cliente y país ---
        st.markdown("##### 3.2. Distribución de Ingresos por Tipo de Cliente y País")
        df_client_country = df_filtered.groupby(['Tipo Cliente', 'Pais'])['Ingreso Total'].sum().reset_index()
        fig_client_country = px.bar(
            df_client_country,
            x='Pais',
            y='Ingreso Total',
            color='Tipo Cliente',
            barmode='stack', # Stacked bars to show total for each country
            title='Ingresos por País y Tipo de Cliente',
            labels={'Ingreso Total': 'Ingreso Total ($)'}
        )
        st.plotly_chart(fig_client_country, use_container_width=True)

        # --- Dashboard Viz 3: Preferencias de plan por tipo de cliente ---
        st.markdown("##### 3.3. Preferencias de Plan por Tipo de Cliente")
        df_plan_client = df_filtered.groupby(['Tipo Cliente', 'Plan'])['ID Cliente'].nunique().reset_index()
        df_plan_client.columns = ['Tipo Cliente', 'Plan', 'Numero de Clientes']

        fig_plan_client = px.bar(
            df_plan_client,
            x='Tipo Cliente',
            y='Numero de Clientes',
            color='Plan',
            barmode='stack',
            title='Número de Clientes por Tipo de Plan y Tipo de Cliente',
            labels={'Numero de Clientes': 'Número de Clientes'}
        )
        st.plotly_chart(fig_plan_client, use_container_width=True)

        st.markdown(
            """
            ---
            **Personalización Visual (Aplicada en Streamlit):**
            * **Colores:** Utiliza las paletas de colores predeterminadas de Plotly Express, que son visualmente agradables.
            * **Interactividad:** Los gráficos de Plotly Express son interactivos por defecto (zoom, pan, hover para detalles). Los filtros en la barra lateral y en la parte superior de esta sección proporcionan interactividad a nivel de datos.
            * **Disposición:** `st.set_page_config(layout="wide")` asegura que la aplicación ocupe el ancho completo de la pantalla.
            """
        )
