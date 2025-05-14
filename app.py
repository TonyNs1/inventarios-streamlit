import os
import streamlit as st
import pandas as pd
from io import BytesIO

# Configuración de la página
st.set_page_config(page_title='Análisis de Inventario', layout='wide')
st.title('📦 Análisis de Inventario')

# Funciones auxiliares
@st.cache_data
def load_data(uploaded):
    df = pd.read_excel(uploaded, header=1)
    df.columns = df.columns.str.strip()
    norm = (df.columns.str.normalize('NFKD')
               .str.encode('ascii', errors='ignore')
               .str.decode('ascii')
               .str.strip()
               .str.lower())
    df.columns = norm
    col_map = {
        'codigo': 'Código', 'nombre': 'Nombre',
        'promedio mensual vendido': 'Promedio mensual', 'promedio mensual': 'Promedio mensual',
        'existencias': 'Existencias',
        'costo ultima compra': 'Último costo', 'ultimo costo unitario con descuento': 'Último costo',
        'ultimo proveedor': 'Último proveedor', 'proveedor': 'Último proveedor'
    }
    return df.rename(columns={k: v for k, v in col_map.items() if k in df.columns}).copy()

@st.cache_data
def compute_suggestions(df, days_min, days_max, margin):
    df = df.copy()
    df['Consumo diario'] = df['Promedio mensual'] / 30
    df['Mínimo sugerido'] = df['Consumo diario'] * days_min
    df['Máximo sugerido'] = df['Consumo diario'] * days_max * (1 + margin/100)
    def estado(e, mn, mx):
        if e <= 0: return '🔴'
        if e < mn: return '🟡'
        if mn <= e <= mx: return '🟢'
        if e <= mx * 1.2: return '🟠'
        return '🔵'
    df['Alerta'] = df.apply(lambda x: estado(x['Existencias'], x['Mínimo sugerido'], x['Máximo sugerido']), axis=1)
    return df

# Carga del archivo
uploaded = st.file_uploader('Cargar archivo Excel', type='xlsx')
if uploaded:
    df = load_data(uploaded)
    # Inicializar df en sesión
    if 'df' not in st.session_state:
        st.session_state.df = df.copy()
    df = st.session_state.df

    # Parámetros en sidebar
    days_min = st.sidebar.slider('Días mínimo', 1, 60, 15, key='days_min')
    days_max = st.sidebar.slider('Días máximo', 1, 90, 30, key='days_max')
    margin = st.sidebar.number_input('Margen extra (%)', 0, 100, 0, key='margin')

    # Calcular sugerencias y alertas
    df_calc = compute_suggestions(df, days_min, days_max, margin)

    # Configurar columnas
    main_cols = ['Código','Nombre','Promedio mensual','Existencias','Mínimo sugerido','Máximo sugerido','Último costo','Último proveedor']
    optional = [c for c in df_calc.columns if c not in main_cols + ['Consumo diario','Alerta']]
    extra = st.sidebar.multiselect('Columnas adicionales', optional, key='extra')

    # Filtros de alerta y proveedor
    alert_opts = ['🔴','🟡','🟢','🟠','🔵']
    alert_filter = st.sidebar.multiselect('Filtrar Alerta', alert_opts, default=alert_opts, key='alert_filter')
    prov_opts = df_calc['Último proveedor'].dropna().unique().tolist()
    prov_filter = st.sidebar.multiselect('Filtrar Proveedor', prov_opts, default=prov_opts, key='prov_filter')

    # Buscar texto
    search = st.sidebar.text_input('Buscar Código/Nombre', key='search')

    # Reiniciar filtros
    if st.sidebar.button('Reiniciar filtros'):
        for k in ['extra','alert_filter','prov_filter','search']:
            if k in st.session_state:
                del st.session_state[k]
        st.session_state.df = df.copy()
        st.rerun()

    # Generar DataFrame filtrado
    display_cols = main_cols + extra + ['Alerta']
    df_disp = df_calc[display_cols]
    df_disp = df_disp[df_disp['Alerta'].isin(alert_filter) & df_disp['Último proveedor'].isin(prov_filter)]
    if search:
        df_disp = df_disp[df_disp['Código'].astype(str).str.contains(search, case=False) |
                          df_disp['Nombre'].str.contains(search, case=False)]

    # Editor inline con eliminación
    editor = df_disp.copy()
    editor.insert(0, 'Eliminar', False)
    cols_e = ['Eliminar','Alerta'] + [c for c in editor.columns if c not in ['Eliminar','Alerta']]
    editor = editor[cols_e]
    edited = st.data_editor(editor, num_rows='dynamic', use_container_width=True)

    # Eliminar filas marcadas
    to_delete = edited[edited['Eliminar']].index.tolist()
    if to_delete:
        st.session_state.df = df.drop(to_delete).reset_index(drop=True)
        st.rerun()

    # Exportar resultados
    csv = df_disp.to_csv(index=False).encode('utf-8')
    excel_buf = BytesIO(); df_disp.to_excel(excel_buf, index=False)
    st.sidebar.download_button('Descargar CSV', csv, 'inventario.csv', 'text/csv')
    st.sidebar.download_button('Descargar Excel', excel_buf.getvalue(), 'inventario.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    # Leyenda de alertas
    st.markdown('**Leyenda de Alertas:**')
    legend = {'🔴':'≤ 0 (Rojo)','🟡':'< mínimo (Amarillo claro)','🟢':'Entre mínimo y máximo (Verde)','🟠':'≤20% sobre máximo (Naranja)','🔵':'>20% sobre máximo (Azul)'}
    for sym, desc in legend.items():
        st.markdown(f"<span style='font-size:20px'>{sym}</span> {desc}", unsafe_allow_html=True)

    # Mostrar solo el editor, no tabla adicional
