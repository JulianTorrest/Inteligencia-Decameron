import streamlit as st
import pandas as pd
import requests
from io import BytesIO
import plotly.express as px
import plotly.graph_objects as go
import numpy as np # For numerical operations, especially with NaN
import locale # For setting locale to ensure correct month names

# Set locale for consistent month names (e.g., 'Enero', 'Febrero')
# This is important for .dt.strftime('%B') to work as expected for Spanish month names
# Try a few common Spanish locales if one doesn't work on your system
try:
    locale.setlocale(locale.LC_ALL, 'es_ES.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'es_CO.UTF-8') # For Colombia specifically
    except locale.Error:
        st.warning("Could not set locale to Spanish. Month names might appear in English or need manual mapping.")
        # Fallback if locale cannot be set, or provide a manual mapping
        MONTH_NAME_MAP = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
            7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }
        # You'd use this in the df transformation: df['Mes Nombre Facturacion'] = df['Mes Facturacion'].map(MONTH_NAME_MAP)


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
                            "3. Dashboard Ejecutivo",
                            "4. Pensamiento Analítico (SQL & Python)",
                            "5. Pensamiento Estratégico (Data Sources)",
                            "6. Análisis de Escenarios y Recomendaciones"]) # New Section

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
        
        # Ensure month names are correct for Spanish locale
        # If locale.setlocale fails, you might need a manual map
        if 'MONTH_NAME_MAP' in globals(): # Check if the fallback map was created
            df['Mes Nombre Facturacion'] = df['Mes Facturacion'].map(MONTH_NAME_MAP).fillna('Desconocido')
        else:
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
        
        # Calculate Net Income (Ingreso Neto)
        df['Ingreso Neto'] = df['Ingreso Total'] - df['Comision']

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
                # Reindex to ensure all 12 months are present, even if some have no sales
                estimated_monthly_budget_2025 = monthly_distribution_ratio.reindex(range(1, 13), fill_value=0) * budget_2025_estimated
                st.session_state['estimated_monthly_budget_2025'] = estimated_monthly_budget_2025.values
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
        ("Ingreso Total por Aerolinea", px.bar(df_transformed.groupby('Aerolinea_Display')['Ingreso Total'].sum().reset_index(), x='Aerolinea_Display', y='Ingreso Total', title='Ingreso Total por Aerolinea', color='Aerolinea_Display')),
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
        ("Ingreso Total por Plan y Aerolinea", px.bar(df_transformed.groupby(['Plan', 'Aerolinea_Display'])['Ingreso Total'].sum().reset_index(), x='Plan', y='Ingreso Total', color='Aerolinea_Display', title='Ingreso Total por Plan Desglosado por Aerolinea'))
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


    st.subheader("D. Cálculo de Comisión por Aerolinea y Destino")
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

# --- SECTION: 4. PENSAMIENTO ANALÍTICO (SQL & Python) ---
elif section == "4. Pensamiento Analítico (SQL & Python)":
    st.header("4. Pensamiento Analítico (SQL & Python)")
    st.write("Esta sección presenta desafíos de pensamiento analítico en SQL y Python.")

    st.markdown("---")
    st.subheader("4.1. Desafío SQL: Identificación de Inconsistencias entre Sistemas")
    st.write("""
    Un grupo hotelero opera con dos sistemas principales: **RESERVAS** y **FACTURACION**.
    Se han detectado inconsistencias entre ambos sistemas, y se requiere una consulta SQL que identifique diferencias significativas.

    **Consideraciones:**
    A. Las coincidencias se basan en los campos: `ID_CLIENTE`, `ID_HABITACION`, `ID_RESERVA`, `FECHA_ENTRADA`.
    B. Se deben mostrar únicamente las diferencias donde el `VALOR` difiera en 50.000 pesos
       o más (positiva o negativa).
    C. También deben incluirse registros que existan en una tabla, pero no en la otra
       (por ejemplo, reservas sin facturación o facturación sin reserva).
    """)

    st.markdown("```sql")
    st.code("""
-- Consulta SQL para identificar inconsistencias entre RESERVAS y FACTURACION

SELECT
    COALESCE(RESERVAS.ID_CLIENTE, FACTURACION.ID_CLIENTE) AS ID_CLIENTE,
    COALESCE(RESERVAS.ID_HABITACION, FACTURACION.ID_HABITACION) AS ID_HABITACION,
    COALESCE(RESERVAS.ID_RESERVA, FACTURACION.ID_RESERVA) AS ID_RESERVA,
    COALESCE(RESERVAS.FECHA_ENTRADA, FACTURACION.FECHA_ENTRADA) AS FECHA_ENTRADA,
    RESERVAS.VALOR AS VALOR_RESERVA,
    FACTURACION.VALOR AS VALOR_FACTURACION,
    (FACTURACION.VALOR - RESERVAS.VALOR) AS DIFERENCIA_VALOR,
    CASE
        WHEN RESERVAS.ID_RESERVA IS NULL THEN 'Facturación sin Reserva'
        WHEN FACTURACION.ID_RESERVA IS NULL THEN 'Reserva sin Facturación'
        WHEN ABS(FACTURACION.VALOR - RESERVAS.VALOR) >= 50000 THEN 'Diferencia de Valor >= 50.000'
        ELSE 'Coincidencia (No Mostrado)' -- Esta categoría no se mostraría debido al filtro WHERE
    END AS TIPO_INCONSISTENCIA
FROM
    RESERVAS
FULL OUTER JOIN
    FACTURACION ON RESERVAS.ID_CLIENTE = FACTURACION.ID_CLIENTE
                 AND RESERVAS.ID_HABITACION = FACTURACION.ID_HABITACION
                 AND RESERVAS.ID_RESERVA = FACTURACION.ID_RESERVA
                 AND RESERVAS.FECHA_ENTRADA = FACTURACION.FECHA_ENTRADA
WHERE
    RESERVAS.ID_RESERVA IS NULL -- Registros solo en FACTURACION
    OR FACTURACION.ID_RESERVA IS NULL -- Registros solo en RESERVAS
    OR ABS(FACTURACION.VALOR - RESERVAS.VALOR) >= 50000; -- Diferencias de valor significativas
    """)
    st.markdown("```")

    st.markdown("""
    **Explicación de la Consulta SQL:**
    * **`FULL OUTER JOIN`**: Esta es la clave para identificar registros que existen en una tabla pero no en la otra. Mantiene todas las filas de ambas tablas, uniendo donde hay coincidencias y colocando `NULL` donde no las hay.
    * **`COALESCE`**: Se usa para seleccionar el primer valor no nulo entre `RESERVAS` y `FACTURACION` para los campos de unión (`ID_CLIENTE`, `ID_HABITACION`, etc.). Esto asegura que los identificadores se muestren incluso si solo existen en una de las tablas.
    * **`DIFERENCIA_VALOR`**: Calcula la resta directa entre `FACTURACION.VALOR` y `RESERVAS.VALOR`.
    * **`TIPO_INCONSISTENCIA`**: Una declaración `CASE` para categorizar el tipo de inconsistencia:
        * **`RESERVAS.ID_RESERVA IS NULL`**: Indica que un registro de `FACTURACION` no tiene una `RESERVA` correspondiente.
        * **`FACTURACION.ID_RESERVA IS NULL`**: Indica que un registro de `RESERVAS` no tiene una `FACTURACION` correspondiente.
        * **`ABS(FACTURACION.VALOR - RESERVAS.VALOR) >= 50000`**: Identifica las filas donde la diferencia absoluta entre los valores es de 50.000 o más.
    * **`WHERE` clause**: Filtra los resultados para mostrar solo las inconsistencias requeridas: registros que son `NULL` en un lado de la unión (existen solo en una tabla) o donde la diferencia de `VALOR` es significativa.
    """)


    st.markdown("---")
    st.subheader("4.2. Desafío Python: Análisis de Crecimiento de Ventas")
    st.write("A continuación, se presenta un fragmento de código en Python. Analiza lo que hace y responde las preguntas.")

    python_code = """
import pandas as pd

df = pd.DataFrame({
 'Cliente': ['A', 'B', 'C', 'D'],
 'Ventas_2024': [100000, 150000, 120000, 130000],
 'Ventas_2025': [130000, 160000, 140000, 125000]
})

df['Crecimiento (%)'] = ((df['Ventas_2025'] - df['Ventas_2024']) / df['Ventas_2024']) * 100

print(df)
    """
    st.code(python_code, language='python')

    # Execute the code to show the output
    st.markdown("##### Output del código original:")
    df_python_original = pd.DataFrame({
     'Cliente': ['A', 'B', 'C', 'D'],
     'Ventas_2024': [100000, 150000, 120000, 130000],
     'Ventas_2025': [130000, 160000, 140000, 125000]
    })
    df_python_original['Crecimiento (%)'] = ((df_python_original['Ventas_2025'] - df_python_original['Ventas_2024']) /
    df_python_original['Ventas_2024']) * 100
    st.dataframe(df_python_original)


    st.markdown("##### B. ¿Qué hace este código paso a paso?")
    st.markdown("""
    Este código Python utiliza la librería `pandas` para realizar un análisis de **crecimiento porcentual de ventas** entre dos años (2024 y 2025) para un conjunto de clientes.

    **Paso a paso:**
    1.  **`import pandas as pd`**: Importa la librería pandas, una herramienta fundamental para la manipulación y análisis de datos en Python, y la renombra como `pd` para facilitar su uso.
    2.  **`df = pd.DataFrame(...)`**: Crea un **DataFrame** de pandas, que es una estructura de datos tabular (similar a una hoja de cálculo). Este DataFrame contiene:
        * Una columna 'Cliente' con identificadores de cliente ('A', 'B', 'C', 'D').
        * Una columna 'Ventas_2024' con los montos de ventas para cada cliente en el año 2024.
        * Una columna 'Ventas_2025' con los montos de ventas para cada cliente en el año 2025.
    3.  **`df['Crecimiento (%)'] = ...`**: Calcula el **crecimiento porcentual** de las ventas para cada cliente y almacena el resultado en una nueva columna llamada 'Crecimiento (%)'. La fórmula utilizada es: `((Ventas_2025 - Ventas_2024) / Ventas_2024) * 100`.
    4.  **`print(df)`**: Imprime en la consola el DataFrame completo, incluyendo la nueva columna 'Crecimiento (%)', mostrando los datos originales junto con el crecimiento calculado para cada uno.

    **En resumen:** El código carga datos de ventas de 2024 y 2025 para varios clientes y calcula el porcentaje de crecimiento (o decrecimiento) de las ventas de 2025 respecto a 2024 para cada uno.
    """)

    st.markdown("##### B. ¿Cómo modificarías el código para que solo muestre los clientes con crecimiento negativo?")
    st.write("Para mostrar solo los clientes con **crecimiento negativo**, necesitamos filtrar el DataFrame basándonos en la columna 'Crecimiento (%)'.")
    st.markdown("```python")
    st.code("""
import pandas as pd

df = pd.DataFrame({
 'Cliente': ['A', 'B', 'C', 'D'],
 'Ventas_2024': [100000, 150000, 120000, 130000],
 'Ventas_2025': [130000, 160000, 140000, 125000]
})

df['Crecimiento (%)'] = ((df['Ventas_2025'] - df['Ventas_2024']) / df['Ventas_2024']) * 100

# Modificación: Filtrar el DataFrame para mostrar solo clientes con crecimiento negativo
df_crecimiento_negativo = df[df['Crecimiento (%)'] < 0]

print(df_crecimiento_negativo)
    """, language='python')
    st.markdown("```")

    st.markdown("##### Output del código modificado:")
    df_python_modified = pd.DataFrame({
     'Cliente': ['A', 'B', 'C', 'D'],
     'Ventas_2024': [100000, 150000, 120000, 130000],
     'Ventas_2025': [130000, 160000, 140000, 125000]
    })
    df_python_modified['Crecimiento (%)'] = ((df_python_modified['Ventas_2025'] - df_python_modified['Ventas_2024']) /
    df_python_modified['Ventas_2024']) * 100
    df_crecimiento_negativo = df_python_modified[df_python_modified['Crecimiento (%)'] < 0]
    st.dataframe(df_crecimiento_negativo)

    st.markdown("""
    **Explicación de la modificación:**
    * **`df[df['Crecimiento (%)'] < 0]`**: Esta línea utiliza la **indexación booleana** de pandas. Crea una serie de valores `True`/`False` donde `True` indica que el crecimiento es negativo. Al pasar esta serie al DataFrame, solo se seleccionan las filas donde la condición es `True`, es decir, solo los clientes con crecimiento negativo. El resultado se guarda en un nuevo DataFrame llamado `df_crecimiento_negativo`.
    """)


# --- SECTION: 5. PENSAMIENTO ESTRATÉGICO (DATA SOURCES) ---
elif section == "5. Pensamiento Estratégico (Data Sources)":
    st.header("5. Pensamiento Estratégico: Data Sources")
    st.write("Una cadena hotelera desea medir la trazabilidad de leads desde la Etapa 1 (Salesforce) hasta la Etapa 3 (ERP - Check-in/Facturación).")

    st.subheader("A. Repositorio de Datos Propuesto y Herramientas")

    st.markdown("""
    Para medir la trazabilidad de leads a través de múltiples sistemas (Salesforce, Sitio Web de Reservas, ERP), propondría un **Data Warehouse (DWH)** como repositorio central. Un DWH está optimizado para consultas analíticas y el reporting, y permitiría consolidar datos históricos de las diferentes etapas del ciclo de vida del cliente.

    ### Descripción del Repositorio de Datos (Data Warehouse)

    El DWH estaría diseñado con un **esquema en estrella o copo de nieve** para facilitar la consulta. Tendría las siguientes tablas principales:

    * **Tabla de Hechos (Fact Table):**
        * **`Fact_Trazabilidad_Lead`**: Contendría métricas clave y las claves foráneas a las tablas de dimensión.
            * `ID_OPORTUNIDAD` (de Salesforce)
            * `ID_RESERVA` (del Sitio Web)
            * `ID_FACTURACION` (del ERP)
            * `Fecha_Creacion_Lead_SK` (Clave de fecha)
            * `Fecha_Reserva_SK` (Clave de fecha)
            * `Fecha_Checkin_SK` (Clave de fecha)
            * `Monto_Oportunidad`
            * `Monto_Reserva`
            * `Monto_Facturado`
            * `Estado_Lead` (Ej: 'Calificado', 'Reservado', 'Facturado', 'Perdido')
            * Métricas de tiempo de transición entre etapas (Ej: `Dias_Lead_a_Reserva`, `Dias_Reserva_a_Checkin`)

    * **Tablas de Dimensión (Dimension Tables):**
        * **`Dim_Cliente`**: Detalles del cliente (ID, Nombre, Contacto, País, etc.).
        * **`Dim_Fecha`**: Una tabla de calendario con atributos de fecha (Año, Mes, Día, Trimestre, Día de la Semana, etc.).
        * **`Dim_Canal`**: Origen del lead (Ej: 'Orgánico', 'Pago', 'Referido').
        * **`Dim_Producto`**: Información sobre los productos/servicios reservados.
        * **`Dim_Propiedad_Hotel`**: Detalles de los hoteles (Nombre, Ubicación, Categoría).

    ---
    ### Propuesta de Herramientas

    1.  **Almacenamiento (Data Warehouse):**
        * **Opción 1 (Cloud): Google BigQuery, Amazon Redshift, Snowflake, Azure Synapse Analytics.**
            * **Ventajas:** Escalabilidad ilimitada, rendimiento optimizado para analítica, mantenimiento reducido, integración nativa con otros servicios en la nube.
            * **Por qué:** Son soluciones modernas, costo-efectivas para grandes volúmenes de datos y cargas de trabajo analíticas.
        * **Opción 2 (On-premise/Managed): PostgreSQL, SQL Server.**
            * **Ventajas:** Control total sobre la infraestructura, familiaridad para equipos con experiencia en bases de datos relacionales.
            * **Consideraciones:** Requiere más gestión de infraestructura y escalabilidad manual.

        * **Recomendación:** Para una cadena hotelera que busca escalabilidad y agilidad, una solución **Cloud Data Warehouse** como **Google BigQuery** o **Snowflake** sería ideal por su capacidad de manejar grandes volúmenes de datos de forma eficiente para fines analíticos.

    2.  **Integración (ETL/ELT):**
        * **Opción 1 (Cloud Native): Google Cloud Dataflow, AWS Glue, Azure Data Factory.**
            * **Ventajas:** Integración profunda con los respectivos ecosistemas cloud, escalabilidad automática, serverless.
        * **Opción 2 (Third-party iPaaS/ETL): Talend, Apache Airflow, Fivetran, Stitch.**
            * **Ventajas:** Conectores pre-construidos para sistemas como Salesforce y Oracle, orquestación de flujos de trabajo complejos, monitoreo.
            * **Por qué:** Permiten automatizar la extracción, transformación y carga (ETL) de datos desde Salesforce, Oracle (Sitio Web de Reservas) y el ERP hacia el Data Warehouse.
        * **Recomendación:** Una combinación de **Fivetran/Stitch** (para la extracción y carga inicial de datos de los sistemas SaaS como Salesforce) y **Apache Airflow** (para orquestar transformaciones más complejas dentro del DWH y monitorear los flujos) sería muy robusta.

    3.  **Visualización (Business Intelligence - BI):**
        * **Opción 1 (Líderes de Mercado): Tableau, Power BI, Looker (Google Looker Studio).**
            * **Ventajas:** Dashboards interactivos, conectividad a múltiples fuentes de datos (incluido el DWH), capacidades avanzadas de visualización y drill-down.
            * **Por qué:** Estas herramientas son excelentes para crear el **Dashboard Ejecutivo** que la gerencia requiere para medir la trazabilidad de leads. Permiten a los usuarios de negocio explorar los datos sin depender del equipo técnico.
        * **Recomendación:** **Looker Studio** (anteriormente Google Data Studio) si el DWH es BigQuery, o **Tableau/Power BI** por su amplia adopción y capacidades.

    4.  **Análisis Predictivo/Prescriptivo:**
        * **Opción 1 (Plataformas ML): Google Cloud AI Platform, AWS SageMaker, Azure Machine Learning.**
            * **Ventajas:** Entornos completos para el ciclo de vida del ML (preparación de datos, entrenamiento, despliegue, monitoreo de modelos), integración con el DWH.
            * **Por qué:** Una vez que los datos de trazabilidad estén en el DWH, se pueden usar para construir modelos que:
                * **Predigan:** La probabilidad de que un lead se convierta en reserva o check-in.
                * **Prescriban:** Recomendaciones para mejorar las tasas de conversión en diferentes etapas (ej: cuándo intervenir con un lead, qué tipo de ofertas ofrecer).
        * **Recomendación:** Si ya están en Google Cloud, **Google Cloud AI Platform** ofrece una suite completa. Para equipos con experiencia en Python, **Jupyter Notebooks** integrados con el DWH son un excelente punto de partida para el desarrollo de modelos, y luego se despliegan en estas plataformas.

    ### Flujo de Datos General

    **Sistemas Fuente** (Salesforce, Oracle Web, ERP)
    $\downarrow$ (Conectores/Integración ETL/ELT - Fivetran/Stitch/Airflow)
    **Data Lake** (Opcional, para datos crudos/estructurados - Cloud Storage)
    $\downarrow$ (Transformación - SQL en DWH o Dataflow)
    **Data Warehouse** (Google BigQuery / Snowflake - Datos limpios, estructurados, modelados)
    $\downarrow$ (Conexión Directa)
    **Herramientas de BI** (Tableau/Power BI/Looker Studio - Dashboards ejecutivos, reportes)
    $\downarrow$ (Conexión a DWH)
    **Plataformas de ML** (Google Cloud AI Platform - Modelos predictivos/prescriptivos)

    Este enfoque asegura una **única fuente de verdad** para los datos, facilita la trazabilidad y permite análisis avanzados.
    """)

# --- NEW SECTION: 6. ANÁLISIS DE ESCENARIOS Y RECOMENDACIONES ---
elif section == "6. Análisis de Escenarios y Recomendaciones":
    st.header("6. Análisis de Escenarios y Recomendaciones")
    st.write("Esta sección presenta análisis de escenarios basados en los datos y ofrece recomendaciones estratégicas para la toma de decisiones.")

    st.markdown("---")
    st.subheader("6.1. Escenario 1: Optimización de Ingresos por Segmento y Plan")
    st.write("Identificar qué combinaciones de **Tipo de Cliente** y **Plan** generan más ingresos y dónde hay oportunidades de crecimiento.")
    
    # Analysis
    df_segment_plan_revenue = df_transformed.groupby(['Tipo Cliente', 'Plan'])['Ingreso Total'].sum().reset_index()
    df_segment_plan_revenue = df_segment_plan_revenue.sort_values(by='Ingreso Total', ascending=False)

    fig_segment_plan = px.bar(
        df_segment_plan_revenue,
        x='Tipo Cliente',
        y='Ingreso Total',
        color='Plan',
        title='Ingreso Total por Tipo de Cliente y Plan',
        labels={'Ingreso Total': 'Ingreso Total ($)'},
        barmode='group'
    )
    st.plotly_chart(fig_segment_plan, use_container_width=True)
    st.dataframe(df_segment_plan_revenue.head(5))

    st.markdown("""
    **Recomendaciones:**
    * **Foco en segmentos de alto valor:** Reforzar las estrategias de marketing y ventas para los **Tipo de Cliente** y **Plan** que actualmente generan los mayores ingresos. Por ejemplo, si "Agencias de Viaje" con "Solo Hotel + Vuelo" son líderes, invertir más en esta relación y en la calidad de estos paquetes.
    * **Explorar upselling/cross-selling:** Para segmentos que tienen un buen volumen de `Room Nights` pero un `Ingreso Total` relativamente bajo, identificar oportunidades para ofrecer planes premium o servicios adicionales que aumenten el valor promedio por reserva.
    """)

    st.markdown("---")
    st.subheader("6.2. Escenario 2: Rentabilidad por Destino (Neto de Comisiones)")
    st.write("Evaluar la rentabilidad real de cada destino después de deducir las comisiones, para identificar los más y menos eficientes.")
    
    # Analysis
    df_destination_profit = df_transformed.groupby('Destino').agg(
        Total_Ingreso=('Ingreso Total', 'sum'),
        Total_Comision=('Comision', 'sum'),
        Ingreso_Neto=('Ingreso Neto', 'sum')
    ).reset_index()
    df_destination_profit = df_destination_profit.sort_values(by='Ingreso_Neto', ascending=False)

    fig_dest_profit = px.bar(
        df_destination_profit,
        x='Destino',
        y=['Total_Ingreso', 'Ingreso_Neto'],
        barmode='group',
        title='Ingreso Total vs. Ingreso Neto por Destino',
        labels={'value': 'Monto ($)', 'variable': 'Tipo de Ingreso'}
    )
    st.plotly_chart(fig_dest_profit, use_container_width=True)
    st.dataframe(df_destination_profit)

    st.markdown("""
    **Recomendaciones:**
    * **Optimización de acuerdos de comisión:** Para destinos con un alto `Total_Ingreso` pero un `Ingreso_Neto` comparativamente bajo (debido a altas comisiones), renegociar los términos con las aerolíneas o agencias para mejorar los márgenes de rentabilidad.
    * **Marketing estratégico para destinos netos:** Dirigir campañas de marketing a los destinos con mayor `Ingreso_Neto`, incluso si su `Ingreso Total` no es el más alto, ya que son más rentables para el negocio.
    """)

    st.markdown("---")
    st.subheader("6.3. Escenario 3: Impacto de la Estacionalidad en Ingresos y Room Nights")
    st.write("Analizar las tendencias mensuales para entender la estacionalidad en ingresos y noches de habitación, crucial para la planificación operativa y de marketing.")
    
    # Analysis
    df_monthly_trends = df_transformed.groupby('Mes Nombre Facturacion').agg(
        Ingreso_Total=('Ingreso Total', 'sum'),
        Room_Nights=('# Room Nights', 'sum')
    ).reset_index()

    # Order months correctly for plotting
    month_order = [
        'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ]
    # Ensure all month names are in the DataFrame or the category definition matches.
    # It's good to re-check actual month names in df_transformed if problem persists.
    # st.write(f"Unique month names in data: {df_transformed['Mes Nombre Facturacion'].unique().tolist()}") # Debugging line

    df_monthly_trends['Mes Nombre Facturacion'] = pd.Categorical(df_monthly_trends['Mes Nombre Facturacion'], categories=month_order, ordered=True)
    df_monthly_trends = df_monthly_trends.sort_values('Mes Nombre Facturacion')

    if df_monthly_trends.empty:
        st.warning("No hay datos de tendencias mensuales disponibles para el análisis de estacionalidad. Revisa los datos de 'Fecha Facturacion'.")
    else:
        fig_monthly_ingreso = px.line(
            df_monthly_trends,
            x='Mes Nombre Facturacion',
            y='Ingreso_Total',
            title='Tendencia Mensual de Ingreso Total',
            markers=True,
            labels={'Ingreso_Total': 'Ingreso Total ($)'}
        )
        st.plotly_chart(fig_monthly_ingreso, use_container_width=True)

        fig_monthly_room_nights = px.line(
            df_monthly_trends,
            x='Mes Nombre Facturacion',
            y='Room_Nights',
            title='Tendencia Mensual de # Room Nights',
            markers=True,
            labels={'Room_Nights': 'Número de Room Nights'}
        )
        st.plotly_chart(fig_monthly_room_nights, use_container_width=True)
        st.dataframe(df_monthly_trends)

    st.markdown("""
    **Recomendaciones:**
    * **Estrategias de precios dinámicos:** Implementar modelos de precios dinámicos que ajusten las tarifas según la demanda estacional, maximizando ingresos durante picos y estimulando la demanda en temporadas bajas.
    * **Campañas de marketing anticipadas:** Lanzar campañas de marketing dirigidas a la venta anticipada para temporadas altas y paquetes atractivos para temporadas bajas, diversificando el flujo de ingresos a lo largo del año.
    """)

    st.markdown("---")
    st.subheader("6.4. Escenario 4: Rendimiento de Agencias de Viaje vs. Directo")
    st.write("Comparar el rendimiento de los clientes que reservan a través de agencias de viaje versus los que reservan directamente.")
    
    # Debugging: Check unique values in 'Tipo Cliente'
    # st.write(f"Unique 'Tipo Cliente' values: {df_transformed['Tipo Cliente'].unique().tolist()}")

    # Analysis: Assume 'Agencias de Viaje' is a 'Tipo Cliente', direct could be 'Cliente Final'
    # Ensure these exact strings exist in your data.
    relevant_client_types = ['Agencias de Viaje', 'Cliente Final'] # Define clearly
    
    # Filter the DataFrame for these specific client types
    df_agency_vs_direct = df_transformed[df_transformed['Tipo Cliente'].isin(relevant_client_types)].groupby('Tipo Cliente').agg(
        Ingreso_Total=('Ingreso Total', 'sum'),
        Numero_Clientes=('ID Cliente', 'nunique'),
        Total_Room_Nights=('# Room Nights', 'sum')
    ).reset_index()

    if df_agency_vs_direct.empty:
        st.warning(f"No hay datos disponibles para 'Agencias de Viaje' o 'Cliente Final'. Revisa los valores únicos en la columna 'Tipo Cliente' de tu dataset. Los valores esperados son: {relevant_client_types}.")
    else:
        fig_agency_direct_revenue = px.bar(
            df_agency_vs_direct,
            x='Tipo Cliente',
            y='Ingreso_Total',
            title='Ingreso Total: Agencias de Viaje vs. Cliente Final',
            labels={'Ingreso_Total': 'Ingreso Total ($)'},
            color='Tipo Cliente'
        )
        st.plotly_chart(fig_agency_direct_revenue, use_container_width=True)
        st.dataframe(df_agency_vs_direct)

    st.markdown("""
    **Recomendaciones:**
    * **Incentivar reserva directa:** Si los clientes directos tienen un valor promedio más alto o menores costos de adquisición (sin comisiones), invertir en la optimización del sitio web, programas de lealtad y ofertas exclusivas para fomentar más reservas directas.
    * **Fortalecer alianzas con agencias:** Si las agencias de viaje aportan un volumen significativo de ingresos, mantener y fortalecer las relaciones con las agencias clave, ofreciéndoles soporte, capacitación y herramientas para vender los paquetes del hotel de manera efectiva.
    """)

    st.markdown("---")
    st.subheader("6.5. Escenario 5: Análisis de Concentración por País de Origen")
    st.write("Identificar si los ingresos están fuertemente concentrados en pocos países de origen y evaluar el riesgo/oportunidad de diversificación.")
    
    # Analysis
    df_country_origin_revenue = df_transformed.groupby('Pais')['Ingreso Total'].sum().reset_index()
    df_country_origin_revenue['Porcentaje'] = (df_country_origin_revenue['Ingreso Total'] / df_country_origin_revenue['Ingreso Total'].sum()) * 100
    df_country_origin_revenue = df_country_origin_revenue.sort_values(by='Ingreso Total', ascending=False)

    fig_country_pie = px.pie(
        df_country_origin_revenue.head(5), # Top 5 for clarity in pie chart
        values='Ingreso Total',
        names='Pais',
        title='Distribución de Ingresos por País de Origen (Top 5)',
        hole=0.3
    )
    st.plotly_chart(fig_country_pie, use_container_width=True)
    st.dataframe(df_country_origin_revenue.head(7)) # Show top 7 in table

    st.markdown("""
    **Recomendaciones:**
    * **Diversificación de mercados:** Si uno o dos países dominan una gran parte de los ingresos, desarrollar planes de marketing y ventas para penetrar o expandirse en mercados de origen menos explotados para reducir la dependencia y el riesgo.
    * **Consolidación en mercados clave:** Continuar invirtiendo en los países de origen principales, pero buscando eficiencias en la adquisición de clientes y mejorando la experiencia para mantener su lealtad y maximizar el valor de vida del cliente.
    """)

    st.markdown("---")
    st.subheader("6.6. Escenario 6: Identificación de Oportunidades en Planes 'Solo Hotel'")
    st.write("Analizar el potencial de upselling para clientes que reservan 'Solo Hotel', identificando oportunidades para ofrecer vuelos o paquetes carreteros.")
    
    # Analysis
    df_solo_hotel = df_transformed[df_transformed['Plan'] == 'Solo Hotel'].groupby('Destino').agg(
        Total_Clientes=('ID Cliente', 'nunique'),
        Ingreso_Solo_Hotel=('Ingreso Total', 'sum')
    ).reset_index()
    df_solo_hotel = df_solo_hotel.sort_values(by='Ingreso_Solo_Hotel', ascending=False)

    fig_solo_hotel_dest = px.bar(
        df_solo_hotel,
        x='Destino',
        y='Ingreso_Solo_Hotel',
        title='Ingreso por Plan "Solo Hotel" por Destino',
        labels={'Ingreso_Solo_Hotel': 'Ingreso Solo Hotel ($)'},
        color='Destino'
    )
    st.plotly_chart(fig_solo_hotel_dest, use_container_width=True)
    st.dataframe(df_solo_hotel)

    st.markdown("""
    **Recomendaciones:**
    * **Paquetes integrados y promociones:** Para reservas de "Solo Hotel", ofrecer proactivamente paquetes que incluyan transporte (vuelo/carretero) o actividades, especialmente para destinos donde el volumen de "Solo Hotel" es alto. Crear promociones específicas para la adición de estos servicios.
    * **Comunicación post-reserva:** Implementar campañas de email marketing o notificaciones push post-reserva (pero pre-check-in) a clientes con plan "Solo Hotel", destacando los beneficios de añadir transporte o excursiones, facilitando la conversión.
    """)

    st.markdown("---")
    st.subheader("6.7. Escenario 7: Eficiencia de Room Nights por Cliente")
    st.write("Analizar el promedio de noches de habitación por cliente para identificar patrones de estancia y oportunidades para extender la duración de las visitas.")
    
    # Analysis
    df_avg_room_nights = df_transformed.groupby('ID Cliente')['# Room Nights'].sum().reset_index()
    avg_room_nights_per_customer = df_avg_room_nights['# Room Nights'].mean()
    
    fig_hist_room_nights = px.histogram(
        df_avg_room_nights,
        x='# Room Nights',
        nbins=20,
        title=f'Distribución de # Room Nights por Cliente (Promedio: {avg_room_nights_per_customer:.2f})',
        labels={'# Room Nights': 'Total Room Nights por Cliente'}
    )
    st.plotly_chart(fig_hist_room_nights, use_container_width=True)
    st.write(f"**Promedio de Room Nights por Cliente:** {avg_room_nights_per_customer:.2f}")

    st.markdown("""
    **Recomendaciones:**
    * **Ofertas de extensión de estancia:** Dirigir promociones específicas a clientes que reservan estancias cortas (por ejemplo, 1-3 noches) para incentivarlos a extender su visita, como "quédate 4 noches, paga 3" o descuentos en días adicionales.
    * **Análisis de segmentos de alta/baja estancia:** Profundizar el análisis para entender qué tipos de clientes (por `Tipo Cliente`, `País`) tienden a tener estancias más cortas o más largas y personalizar las ofertas en consecuencia.
    """)

    st.markdown("---")
    st.subheader("6.8. Escenario 8: Desempeño de Aerolíneas Socias")
    st.write("Evaluar qué aerolíneas asociadas contribuyen más a los ingresos, especialmente para planes que incluyen vuelo, y cómo optimizar estas alianzas.")
    
    # Analysis
    df_airline_revenue = df_transformed.groupby('Aerolinea_Display')['Ingreso Total'].sum().reset_index()
    df_airline_revenue = df_airline_revenue.sort_values(by='Ingreso Total', ascending=False)

    fig_airline_revenue = px.bar(
        df_airline_revenue.head(10), # Show top 10 for clarity
        x='Aerolinea_Display',
        y='Ingreso Total',
        title='Ingreso Total por Aerolínea (Top 10)',
        labels={'Ingreso Total': 'Ingreso Total ($)', 'Aerolinea_Display': 'Aerolínea'},
        color='Aerolinea_Display'
    )
    st.plotly_chart(fig_airline_revenue, use_container_width=True)
    st.dataframe(df_airline_revenue.head(10))

    st.markdown("""
    **Recomendaciones:**
    * **Fortalecer alianzas estratégicas:** Priorizar y profundizar las relaciones con las aerolíneas que demuestran ser las mayores generadoras de ingresos, buscando acuerdos de marketing conjuntos o tarifas preferenciales para paquetes.
    * **Explorar nuevas rutas/aerolíneas:** Para destinos con bajo volumen de paquetes con vuelo, investigar la posibilidad de establecer alianzas con nuevas aerolíneas o promocionar rutas existentes para aumentar la accesibilidad y el flujo de clientes.
    """)

    st.markdown("---")
    st.subheader("6.9. Escenario 9: Potencial de Crecimiento en Mercados Emisivos")
    st.write("Evaluar el rendimiento de los mercados emisivos (clientes de un país diferente al destino) y el potencial de expansión.")
    
    # Analysis
    df_mercado = df_transformed.groupby('Mercado')['Ingreso Total'].sum().reset_index()
    df_mercado_detail = df_transformed[df_transformed['Mercado'] == 'Emisivo'].groupby(['Pais', 'Destino'])['Ingreso Total'].sum().reset_index()
    df_mercado_detail = df_mercado_detail.sort_values(by='Ingreso Total', ascending=False)

    fig_mercado_dist = px.pie(
        df_mercado,
        values='Ingreso Total',
        names='Mercado',
        title='Distribución de Ingresos por Tipo de Mercado',
        hole=0.3
    )
    st.plotly_chart(fig_mercado_dist, use_container_width=True)

    st.markdown("""
    **Recomendaciones:**
    * **Inversión en marketing internacional:** Si el mercado emisivo representa una porción significativa, aumentar la inversión en marketing digital y presencia en ferias turísticas internacionales dirigidas a los países emisores clave.
    * **Ofertas personalizadas para mercados emisivos:** Desarrollar paquetes y promociones específicas que se adapten a las preferencias culturales y patrones de viaje de los clientes de los mercados emisivos más importantes.
    """)

    st.markdown("---")
    st.subheader("6.10. Escenario 10: Optimización de Estrategias para Clientes Corporativos")
    st.write("Analizar el comportamiento y el valor de los clientes 'Corporativo' para diseñar estrategias que maximicen este segmento.")
    
    # Analysis
    df_corporate = df_transformed[df_transformed['Tipo Cliente'] == 'Corporativo'].groupby('Destino').agg(
        Total_Reservas=('ID Cliente', 'count'), # Count of bookings from corporate
        Ingreso_Corporativo=('Ingreso Total', 'sum'),
        Avg_Room_Nights=('# Room Nights', 'mean') # Changed to '# Room Nights' for consistency
    ).reset_index()
    df_corporate = df_corporate.sort_values(by='Ingreso_Corporativo', ascending=False)

    fig_corporate_revenue = px.bar(
        df_corporate,
        x='Destino',
        y='Ingreso_Corporativo',
        title='Ingreso Total de Clientes Corporativos por Destino',
        labels={'Ingreso_Corporativo': 'Ingreso Corporativo ($)'},
        color='Destino'
    )
    st.plotly_chart(fig_corporate_revenue, use_container_width=True)
    st.dataframe(df_corporate)

    st.markdown("""
    **Recomendaciones:**
    * **Programas de fidelización corporativos:** Implementar programas de lealtad diseñados específicamente para empresas, ofreciendo tarifas preferenciales, beneficios exclusivos para sus empleados o espacios para eventos.
    * **Canales de venta directa B2B:** Fortalecer los canales de venta directa a empresas, asignando ejecutivos de cuenta que gestionen las relaciones y comprendan las necesidades específicas del sector corporativo (ej. viajes de negocios, eventos, capacitaciones).
    """)

````
