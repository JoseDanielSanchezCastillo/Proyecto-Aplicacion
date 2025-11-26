# Cargar bibliotecas requeridas
import os
import streamlit as st
import geopandas as gpd
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import folium
from folium.plugins import MeasureControl
from streamlit_folium import st_folium
from shapely.geometry import Point
from haversine import haversine, Unit
import requests
import json

# Solucionar el problema de memory leak 
os.environ['OMP_NUM_THREADS'] = '1'

# Configuración de pandas
pd.set_option('display.float_format', '{:,.2f}'.format)

# Configuración del sitio web
st.set_page_config(
    page_title="Centros Educativos de Costa Rica",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="expanded"
)

def normalizar_texto(texto):
    """Normalizar el texto para comparación en los filtros"""
    if not isinstance(texto, str):
        return ""
    return texto.strip().lower().replace(' ', '')

def calcular_distancia(latitud1, longitud1, latitud2, longitud2):
    """Calcular distancia entre dos puntos """
    punto1 = (latitud1, longitud1)
    punto2 = (latitud2, longitud2)
    return haversine(punto1, punto2, unit=Unit.KILOMETERS)

@st.cache_data
def simplificar_geometrias(_geodataframe, tolerancia=0.001):
    """
        Simplifica las geometrías del GeoDataFrame para mejorar el rendimiento.
        Tolerancia de 0.001° (aproximadamente 100 metros).
    """
    geodataframe_simplificado = _geodataframe.copy()
    geodataframe_simplificado['geometry'] = geodataframe_simplificado['geometry'].simplify(
        tolerance=tolerancia, 
        preserve_topology=True
    )
    return geodataframe_simplificado

@st.cache_data
def cargar_datos():
    """Función para cargar datos con caché"""

    try:
        cantones_gdf = gpd.read_file('datos/cantones.gpkg')
        centro_educativos_df = pd.read_csv('datos/centros_educativos.csv')
        poblacion_vivienda_canton_df = pd.read_csv('datos/poblacion_vivienda_canton.csv', encoding='latin-1')
        
        centro_educativos_gdf = gpd.GeoDataFrame(
            centro_educativos_df, 
            geometry=gpd.points_from_xy(centro_educativos_df.LONGITUD, centro_educativos_df.LATITUD),
            crs='EPSG:4326'
        )
        
        # Operaciones espaciales entre cantones y centros educativos
        total_centro_educativos = gpd.sjoin(centro_educativos_gdf, cantones_gdf, how='left', predicate='within')
        total_centro_educativos_publicos = gpd.sjoin(
            centro_educativos_gdf[centro_educativos_gdf['TIPO_INSTI'] == 'PÚBLICO'], 
            cantones_gdf, how='left', predicate='within'
        )
        total_centro_educativos_privados = gpd.sjoin(
            centro_educativos_gdf[centro_educativos_gdf['TIPO_INSTI'] == 'PRIVADO'], 
            cantones_gdf, how='left', predicate='within'
        )
        
        # Conteos de cantones
        total_centro_educativos = total_centro_educativos.groupby('CANTÓN').size().reset_index(name='TOTAL_CENTROS_EDUCATIVOS')
        total_centro_educativos_publicos = total_centro_educativos_publicos.groupby('CANTÓN').size().reset_index(name='TOTAL_CENTROS_EDUCATIVOS_PUBLICOS')
        total_centro_educativos_privados = total_centro_educativos_privados.groupby('CANTÓN').size().reset_index(name='TOTAL_CENTROS_EDUCATIVOS_PRIVADO')
        
        # Combinar cantones con conteos   
        cantones_centros_educativos_gdf = cantones_gdf.merge(total_centro_educativos, on='CANTÓN', how='left')
        cantones_centros_educativos_gdf = cantones_centros_educativos_gdf.merge(total_centro_educativos_publicos, on='CANTÓN', how='left')
        cantones_centros_educativos_gdf = cantones_centros_educativos_gdf.merge(total_centro_educativos_privados, on='CANTÓN', how='left')
        
        poblacion_vivienda_canton_df = poblacion_vivienda_canton_df.drop(columns=['PROVINCIA'])
        cantones_centros_educativos_gdf = cantones_centros_educativos_gdf.merge(poblacion_vivienda_canton_df, on='CANTÓN', how='left')

        # Cálculos de área y densidad
        cantones_centros_educativos_crtm05_gdf = cantones_centros_educativos_gdf.to_crs(epsg=5367)
        cantones_centros_educativos_crtm05_gdf['AREA_M2'] = cantones_centros_educativos_crtm05_gdf.geometry.area
        cantones_centros_educativos_crtm05_gdf['AREA_KM2'] = cantones_centros_educativos_crtm05_gdf['AREA_M2'] / 1000000
        cantones_centros_educativos_crtm05_gdf['DENSIDAD_CENTROS_EDUCATIVOS_KM2'] = (
            cantones_centros_educativos_crtm05_gdf['TOTAL_CENTROS_EDUCATIVOS'] / cantones_centros_educativos_crtm05_gdf['AREA_KM2']
        )
        cantones_centros_educativos_crtm05_gdf['DENSIDAD_POBLACIONAL_KM2'] = (
            cantones_centros_educativos_crtm05_gdf['POBLACION TOTAL'] / cantones_centros_educativos_crtm05_gdf['AREA_KM2']
        )
        cantones_centros_educativos_crtm05_gdf['CENTROS_EDUCATIVOS_10K_HABITANTES'] = (
            cantones_centros_educativos_crtm05_gdf['TOTAL_CENTROS_EDUCATIVOS'] / 
            cantones_centros_educativos_crtm05_gdf['POBLACION TOTAL']
        ) * 10000

        return cantones_centros_educativos_crtm05_gdf, centro_educativos_gdf
        
    except Exception as e:
        st.error(f"Ha ocurrido un error al cargar los datos: {e}")
        return None, None

# ============================================================================
# Funciones para la creacion de tablas, gráficos y mapas
# ============================================================================

def crear_tabla(centros_educativos, provincia):
    """Tabla interactiva de Centros Educativos de Costa Rica"""

    if len(centros_educativos) == 0 and provincia != 'Todas':
        st.warning(f"No se encontraron Centros Educativos para la provincia: {provincia}")
        return
    
    if not centros_educativos.empty:
        tabla_centros = centros_educativos[['CODSABER', 'CENTRO_EDU', 'TIPO_INSTI', 'REGIONAL', 'CIRCUITO', 'PROVINCIA', 'CANTON', 'DISTRITO', 'POBLADO', 'DIRECCION']].copy()
        
        st.dataframe(
            tabla_centros,
            width='stretch',
            height=500,
            hide_index=True,
            column_config={
                'CODSABER': st.column_config.TextColumn("Código Saber"),
                'CENTRO_EDU': st.column_config.TextColumn("Centro Educativo"),
                'TIPO_INSTI': st.column_config.TextColumn("Tipo de Institución"),
                'REGIONAL': st.column_config.TextColumn("Regional"),
                'CIRCUITO': st.column_config.TextColumn("Circuito"),
                'PROVINCIA': st.column_config.TextColumn("Provincia"),
                'CANTON': st.column_config.TextColumn("Cantón"),
                'DISTRITO': st.column_config.TextColumn("Distrito"),
                'POBLADO': st.column_config.TextColumn("Poblado"),
                'DIRECCION': st.column_config.TextColumn("Dirección")
            }
        )

@st.cache_data
def crear_grafico_densidad_centros(_cantones):
    """Gráfico comparativo de densidad y total de centros educativos por cantón"""

    if _cantones.empty or len(_cantones) <= 1:
        return None
    
    # Ordenar cantones por densidad de centros educativos
    cantones_ordenados = _cantones.sort_values('DENSIDAD_CENTROS_EDUCATIVOS_KM2', ascending=False)
    
    grafico = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Traza de barras para la densidad de centros educativos
    grafico.add_trace(
        go.Bar(x=cantones_ordenados['CANTÓN'], 
               y=cantones_ordenados['DENSIDAD_CENTROS_EDUCATIVOS_KM2'],
               name='Densidad (centros educativos/km²)',
               marker_color='#84bce0'),
        secondary_y=False,
    )
    
    # Traza de linea para el total de centros educativos
    grafico.add_trace(
        go.Scatter(x=cantones_ordenados['CANTÓN'], 
                   y=cantones_ordenados['TOTAL_CENTROS_EDUCATIVOS'],
                   name='Total de centros educativos',
                   line=dict(color='#101b49', width=2),
                   mode='lines+markers'),
        secondary_y=True,
    )
    
    # Configuración del layout
    grafico.update_layout(
        title_text='Densidad por km² y total de centros educativos por cantón',
        xaxis_tickangle=-45,
        height=500,
        showlegend=True
    )
    
    grafico.update_xaxes(title_text="Cantón")
    grafico.update_yaxes(title_text="Densidad (centros educativos/km²)", secondary_y=False)
    grafico.update_yaxes(title_text="Total de centros educativos", secondary_y=True)
    
    return grafico

@st.cache_data
def crear_grafico_densidad_poblacional(_cantones):
    """Gráfico comparativo de densidad poblacional y total de centros educativos por cantón"""

    if _cantones.empty or len(_cantones) <= 1:
        return None
    
    # Ordenar cantones por densidad poblacional
    cantones_ordenados = _cantones.sort_values('DENSIDAD_POBLACIONAL_KM2', ascending=False)
    
    grafico = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Traza de barras para la densidad de centros educativos
    grafico.add_trace(
        go.Bar(x=cantones_ordenados['CANTÓN'], 
               y=cantones_ordenados['DENSIDAD_POBLACIONAL_KM2'],
               name='Densidad poblacional (habitantes/km²)',
               marker_color='#84bce0'),
        secondary_y=False,
    )
    
    # Traza de linea para el total de centros educativos
    grafico.add_trace(
        go.Scatter(x=cantones_ordenados['CANTÓN'], 
                   y=cantones_ordenados['TOTAL_CENTROS_EDUCATIVOS'],
                   name='Total de centros educativos',
                   line=dict(color='#101b49', width=2),
                   mode='lines+markers'),
        secondary_y=True,
    )
    
    grafico.update_layout(
        title_text='Densidad poblacional y total de centros educativos por cantón',
        xaxis_tickangle=-45,
        height=500,
        showlegend=True
    )
    
    grafico.update_xaxes(title_text="Cantón")
    grafico.update_yaxes(title_text="Densidad poblacional (habitantes/km²)", secondary_y=False)
    grafico.update_yaxes(title_text="Total de Centros Educativos", secondary_y=True)
    
    return grafico

def crear_mapa(cantones_gdf, centros_educativos, tipo_institucion='Todos'):

    # Convertir cantones a WGS84
    cantones_wgs84 = cantones_gdf.to_crs(epsg=4326)
    cantones_simple = simplificar_geometrias(cantones_wgs84, tolerancia=0.002)
    
    # Redondear valores para mejorar visualización
    cantones_simple = cantones_simple.copy()
    cantones_simple['Densidad (centros/km²)'] = cantones_simple['DENSIDAD_CENTROS_EDUCATIVOS_KM2'].round(4)
    cantones_simple['Centros por 10k hab'] = cantones_simple['CENTROS_EDUCATIVOS_10K_HABITANTES'].round(2)
    cantones_simple['Área (km²)'] = cantones_simple['AREA_KM2'].round(2)
    cantones_simple['Densidad Poblacional (hab/km²)'] = cantones_simple['DENSIDAD_POBLACIONAL_KM2'].round(2)
    cantones_simple['Total Centros'] = cantones_simple['TOTAL_CENTROS_EDUCATIVOS'].fillna(0).astype(int)
    cantones_simple['Centros Públicos'] = cantones_simple['TOTAL_CENTROS_EDUCATIVOS_PUBLICOS'].fillna(0).astype(int)
    cantones_simple['Centros Privados'] = cantones_simple['TOTAL_CENTROS_EDUCATIVOS_PRIVADO'].fillna(0).astype(int)
    
    # Crear mapa base
    m = folium.Map(
        location=[9.9281, -84.0907],
        zoom_start=8,
        control_scale=True,
        tiles='OpenStreetMap'
    )
    
    # Capa 1: Densidad de centros educativos por cantón
    cantones_simple.explore(
        m=m,
        column='Densidad (centros/km²)',
        cmap='YlOrRd',
        legend=True,
        legend_kwds={'caption': 'Densidad de centros educativos (centros/km²)'},
        tooltip=['CANTÓN', 'PROVINCIA', 'Total Centros', 'Centros Públicos', 
                 'Centros Privados', 'Densidad (centros/km²)'],
        popup=['CANTÓN', 'PROVINCIA', 'Total Centros', 'Centros Públicos', 
               'Centros Privados', 'Densidad (centros/km²)'],
        style_kwds={
            'fillOpacity': 0.6,
            'weight': 1,
            'color': 'gray'
        },
        highlight_kwds={
            'fillOpacity': 0.9,
            'weight': 3,
            'color': 'black'
        },
        name='Densidad de centros educativos por cantón',
        show=False
    )
    
    # Capa 2: Centros Educativos por cada 10000 habitantes 
    cantones_simple.explore(
        m=m,
        column='Centros por 10k hab',
        cmap='YlGnBu',
        legend=True,
        legend_kwds={'caption': 'Centros educativos por 10,000 habitantes'},
        tooltip=['CANTÓN', 'PROVINCIA', 'Total Centros', 'Centros Públicos', 
                 'Centros Privados', 'Centros por 10k hab'],
        popup=['CANTÓN', 'PROVINCIA', 'Total Centros', 'Centros Públicos', 
               'Centros Privados', 'Centros por 10k hab'],
        style_kwds={
            'fillOpacity': 0.6, 
            'weight': 1,
            'color': 'gray'
        },
        highlight_kwds={
            'fillOpacity': 0.9,
            'weight': 3,
            'color': 'black'
        },
        name='Centros educativos por cada 10k habitantes',
        show=False
    )
    
    # Capa 3: Centros educativos públicos
    if tipo_institucion in ['Todos', 'PÚBLICO']:

        centros_publicos = centros_educativos[centros_educativos['TIPO_INSTI'] == 'PÚBLICO']
        marcadores_centros_publicos = folium.FeatureGroup(name='Centros Educativos Públicos', show=True)
        
        for _, centro in centros_publicos.iterrows():
            contenido = f"""
            <b>{centro['CENTRO_EDU']}</b><br>
            Tipo: {centro['TIPO_INSTI']}<br>
            Cantón: {centro['CANTON']}<br>
            Distrito: {centro['DISTRITO']}
            """
            
            folium.CircleMarker(
                location=[centro['LATITUD'], centro['LONGITUD']],
                radius=5,
                popup=folium.Popup(contenido, max_width=200, lazy=True),
                tooltip=centro['CENTRO_EDU'],
                color='#3388ff',
                fill=True,
                fillColor='#3388ff',
                fillOpacity=0.6,
                weight=1
            ).add_to(marcadores_centros_publicos)
        
        marcadores_centros_publicos.add_to(m)
    
    # Capa 4: Centros educativos privados
    if tipo_institucion in ['Todos', 'PRIVADO']:
        centros_privados = centros_educativos[centros_educativos['TIPO_INSTI'] == 'PRIVADO']
        marcadores_centros_privados = folium.FeatureGroup(name='Centros Educativos Privados', show=True)
        
        for _, centro in centros_privados.iterrows():
            contenido = f"""
            <b>{centro['CENTRO_EDU']}</b><br>
            Tipo: {centro['TIPO_INSTI']}<br>
            Cantón: {centro['CANTON']}<br>
            Distrito: {centro['DISTRITO']}
            """
            
            folium.CircleMarker(
                location=[centro['LATITUD'], centro['LONGITUD']],
                radius=5,
                popup=folium.Popup(contenido, max_width=200, lazy=True),
                tooltip=centro['CENTRO_EDU'],
                color='#ff6b6b',
                fill=True,
                fillColor='#ff6b6b',
                fillOpacity=0.6,
                weight=1
            ).add_to(marcadores_centros_privados)
        
        marcadores_centros_privados.add_to(m)
    
    # Control de medición
    MeasureControl(
        position='topleft',
        primary_length_unit='kilometers',
        secondary_length_unit='meters',
    ).add_to(m)
    
    # Control de capas
    folium.LayerControl(collapsed=True).add_to(m)
    
    return m

def crear_mapa_busqueda(centro_mapa, zoom, ubicacion_coords, centros_cercanos, centro_coords, centro_seleccionado, centros_gdf):
    """ Mapa de búsqueda"""

    m = folium.Map(
        location=centro_mapa,
        zoom_start=zoom,
        control_scale=True,
        prefer_canvas=True,
        tiles='OpenStreetMap'
    )
    
    # Marcador de ubicación buscada (origen) y buffer de 1 km
    if ubicacion_coords:
        folium.Marker(
            ubicacion_coords,
            popup="Ubicación seleccionada",
            tooltip="Ubicación seleccionada",
            icon=folium.Icon(color='red', icon='home', prefix='fa')
        ).add_to(m)
        
        # Dibujar el circulo del buffer
        folium.Circle(
            location=ubicacion_coords,
            radius=1000,
            color='#3388ff',
            fill=True,
            fillColor='#3388ff',
            fillOpacity=0.1,
            weight=2,
            dash_array='5, 10',
            popup='Radio de búsqueda: 1 km',
            tooltip='Radio de búsqueda: 1 km'
        ).add_to(m)
    
    # Lista de todos los centros educativos cercanos
    if centros_cercanos is not None and len(centros_cercanos) > 0:
        for _, centro in centros_cercanos.iterrows():
            if centro['TIPO_INSTI'] == 'PÚBLICO':
                color_icono = 'blue'
            else:
                color_icono = 'lightred'
            
            popup_html = f"""
            <b>{centro['CENTRO_EDU']}</b><br>
            Tipo: {centro['TIPO_INSTI']}<br>
            Cantón: {centro['CANTON']}<br>
            Distancia del origen: {centro['DISTANCIA_KM']:.2f} km
            """
            
            folium.Marker(
                [centro['LATITUD'], centro['LONGITUD']],
                popup=folium.Popup(popup_html, max_width=250, lazy=True),
                tooltip=f"{centro['CENTRO_EDU']} ({centro['DISTANCIA_KM']:.2f} km)",
                icon=folium.Icon(color=color_icono, icon='school', prefix='fa')
            ).add_to(m)
    
    # Centro seleccionado
    if centro_coords and centro_seleccionado != 'Seleccione':
        centro_data = centros_gdf[centros_gdf['CENTRO_EDU'] == centro_seleccionado].iloc[0]
        
        popup_html = f"""
        <b>{centro_data['CENTRO_EDU']}</b><br>
        Tipo: {centro_data['TIPO_INSTI']}<br>
        Cantón: {centro_data['CANTON']}<br>
        <i>Centro seleccionado</i>
        """
        
        if centro_data['TIPO_INSTI'] == 'PÚBLICO':
            color_icono = 'blue'
        else:
            color_icono = 'lightred'
        
        folium.Marker(
            centro_coords,
            popup=folium.Popup(popup_html, max_width=250, lazy=True),
            tooltip=f"{centro_data['CENTRO_EDU']}",
            icon=folium.Icon(color=color_icono, icon='school', prefix='fa')
        ).add_to(m)
    
    folium.LayerControl(collapsed=True).add_to(m)
    
    return m

# ============================================================================
# Fragmentos de la aplicación: Tabla, gráficos y mapas
# ============================================================================

@st.fragment
def fragmento_tabla(centros_educativos_filtrados, provincia_seleccionada):
    """Fragmento para la tabla."""
    
    st.subheader("Registro de Centros Educativos de Costa Rica")
    crear_tabla(centros_educativos_filtrados, provincia_seleccionada)

@st.fragment
def fragmento_graficos(cantones_filtrados):
    """Fragmento para ambos gráficos con pestañas"""

    st.subheader("Gráficos comparativos")

    # Crear pestañas
    pestana1, pestana2 = st.tabs(["Densidad de Centros", "Densidad Poblacional"])
    
    # Grafico de densidad por km² y el total de Centros Educativos
    with pestana1:
        st.markdown("### Comparación entre la densidad por km² y el total de Centros Educativos por cantón")
        grafico = crear_grafico_densidad_centros(cantones_filtrados)
        if grafico:
            st.plotly_chart(grafico, width='stretch')
        else:
            st.warning("No hay suficientes datos para generar el gráfico")
    
    # Grafico de densidad poblacional y el total de Centros Educativos
    with pestana2:
        st.markdown("### Comparación entre la densidad poblacional y el total de Centros Educativos por cantón")
        grafico = crear_grafico_densidad_poblacional(cantones_filtrados)
        if grafico:
            st.plotly_chart(grafico, width='stretch')
        else:
            st.warning("No hay suficientes datos para generar el gráfico")

@st.fragment
def fragmento_mapa(cantones_filtrados, centros_educativos_filtrados, tipo_institucion):
    """Fragmento para el mapa"""
    
    st.subheader("Distribución y densidad de Centros Educativos por cantón")
    
    if not cantones_filtrados.empty:
        mapa = crear_mapa(
            cantones_filtrados, 
            centros_educativos_filtrados, 
            tipo_institucion
        )
        st_folium(mapa, width='stretch', height=650, returned_objects=[])
    else:
        st.warning("No hay datos de cantones para mostrar")

@st.fragment
def fragmento_busqueda(centros_gdf):
    """Fragmento de búsqueda de centros educativos"""

    st.subheader("Búsqueda de Centros Educativos")
    
    # Inicializar variables de sesión
    if 'busqueda_sugerencias' not in st.session_state:
        st.session_state.busqueda_sugerencias = []
    if 'busqueda_direccion_seleccionada' not in st.session_state:
        st.session_state.busqueda_direccion_seleccionada = None
    if 'busqueda_ubicacion_coordenadas' not in st.session_state:
        st.session_state.busqueda_ubicacion_coordenadas = None
    if 'busqueda_centros_cercanos' not in st.session_state:
        st.session_state.busqueda_centros_cercanos = None
    if 'busqueda_centro_coordenadas' not in st.session_state:
        st.session_state.busqueda_centro_coordenadas = None
    if 'busqueda_centro_seleccionado' not in st.session_state:
        st.session_state.busqueda_centro_seleccionado = 'Seleccione'
    if 'busqueda_tipo_activo' not in st.session_state:
        st.session_state.busqueda_tipo_activo = None
    
    # Pestaña para los dos tipos de búsqueda
    pestana_ubicacion, pestana_centro = st.tabs(["Búsqueda por ubicación", "Búsqueda por nombre"])
    
    with pestana_ubicacion:
        
        direccion_entrada = st.text_input(
            "Ingrese una dirección en Costa Rica:", 
            placeholder="Ejemplo: San José, Costa Rica",
            key="busqueda_direccion_entrada"
        )
        
        # Servicio de Openstreetmap para geocodificación de ubicaciones a partir de una dirección
        if direccion_entrada and len(direccion_entrada) >= 3:
            try:
                respuesta = requests.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={'q': direccion_entrada, 'format': 'json', 'limit': 5, 'countrycodes': 'cr'},
                    headers={'User-Agent': 'StreamlitApp/1.0'},
                    timeout=3
                )
                
                # Procesar la respuesta
                if respuesta.status_code == 200:
                    resultado = respuesta.json()
                    st.session_state.busqueda_sugerencias = [
                        {'display': r['display_name'], 'lat': float(r['lat']), 'lon': float(r['lon'])}
                        for r in resultado
                    ]
            except Exception:
                pass
        
        # Mostrar sugerencias de ubicaciones
        if st.session_state.busqueda_sugerencias:
            opciones = ['Seleccione'] + [s['display'] for s in st.session_state.busqueda_sugerencias]
            seleccion = st.selectbox("Sugerencias:", opciones, key="busqueda_select_sug")
            
            # Seleccionar la dirección seleccionada
            if seleccion != 'Seleccione':
                st.session_state.busqueda_direccion_seleccionada = next(
                    (s for s in st.session_state.busqueda_sugerencias if s['display'] == seleccion), None
                )
        
        btn_buscar = st.button("Buscar", key="busqueda_btn")
        
        # Procesar búsqueda por ubicación
        if btn_buscar and st.session_state.busqueda_direccion_seleccionada:
            st.session_state.busqueda_centro_coords = None
            st.session_state.busqueda_centro_seleccionado = 'Seleccione'
            st.session_state.busqueda_tipo_activo = 'ubicacion'
            
            lat = st.session_state.busqueda_direccion_seleccionada['lat']
            lon = st.session_state.busqueda_direccion_seleccionada['lon']
            st.session_state.busqueda_ubicacion_coords = (lat, lon)

            # Radio de búsqueda de 1 km
            radio = 0.01

            # Filtrar centros educativos cercanos
            centros_educativos_cercanos = centros_gdf[
                (centros_gdf['LATITUD'].between(lat - radio, lat + radio)) &
                (centros_gdf['LONGITUD'].between(lon - radio, lon + radio))
            ].copy()
            
            centros_educativos_cercanos['DISTANCIA_KM'] = centros_educativos_cercanos.apply(
                lambda r: calcular_distancia(lat, lon, r['LATITUD'], r['LONGITUD']), axis=1
            )
            centros_educativos_cercanos = centros_educativos_cercanos[centros_educativos_cercanos['DISTANCIA_KM'] <= 1.0].sort_values('DISTANCIA_KM')
            st.session_state.busqueda_centros_cercanos = centros_educativos_cercanos
            st.success(f"Se identificaron {len(centros_educativos_cercanos)} centros educativos en un radio de 1km")
        
        # Mostrar mapa de resultados
        if st.session_state.busqueda_tipo_activo == 'ubicacion' and st.session_state.busqueda_ubicacion_coords:
            st.markdown("---")
            
            mapa = crear_mapa_busqueda(
                st.session_state.busqueda_ubicacion_coords, 14,
                st.session_state.busqueda_ubicacion_coords,
                st.session_state.busqueda_centros_cercanos,
                None, 'Seleccione', centros_gdf
            )
            st_folium(mapa, width='stretch', height=500, returned_objects=[])
            
            # Tabla de resultados
            if st.session_state.busqueda_centros_cercanos is not None and len(st.session_state.busqueda_centros_cercanos) > 0:
                st.dataframe(
                    st.session_state.busqueda_centros_cercanos[
                        ['CENTRO_EDU', 'TIPO_INSTI', 'CANTON', 'DISTRITO', 'DISTANCIA_KM']
                    ],
                    width='stretch',
                    hide_index=True,
                    column_config={
                        'CENTRO_EDU': "Centro Educativo",
                        'TIPO_INSTI': "Tipo",
                        'CANTON': "Cantón",
                        'DISTRITO': "Distrito",
                        'DISTANCIA_KM': st.column_config.NumberColumn("Distancia (km)", format="%.2f")
                    }
                )
    
    with pestana_centro:
        
        centros_lista = centros_gdf.sort_values('CENTRO_EDU')['CENTRO_EDU'].unique().tolist()

        # Seleccionar el centro educativo a partir de una lista desplegable
        centro_seleccionado = st.selectbox(
            "Seleccione un Centro Educativo:", 
            ['Seleccione'] + centros_lista,
            key="busqueda_select_centro"
        )
        btn_busqueda_centro = st.button("Mostrar en mapa", key="busqueda_btn_centro")
        
        # Procesar búsqueda por centro
        if btn_busqueda_centro and centro_seleccionado != 'Seleccione':
            st.session_state.busqueda_ubicacion_coords = None
            st.session_state.busqueda_centros_cercanos = None
            st.session_state.busqueda_tipo_activo = 'centro'
            
            centro_data = centros_gdf[centros_gdf['CENTRO_EDU'] == centro_seleccionado].iloc[0]
            st.session_state.busqueda_centro_coords = (centro_data['LATITUD'], centro_data['LONGITUD'])
            st.session_state.busqueda_centro_seleccionado = centro_seleccionado
            st.success(f"Centro Educativo localizado: {centro_seleccionado}")
        
        # Mostrar mapa para búsqueda por centro
        if st.session_state.busqueda_tipo_activo == 'centro' and st.session_state.busqueda_centro_coords:
            st.markdown("---")
            
            mapa = crear_mapa_busqueda(
                st.session_state.busqueda_centro_coords, 15,
                None, None,
                st.session_state.busqueda_centro_coords,
                st.session_state.busqueda_centro_seleccionado,
                centros_gdf
            )
            st_folium(mapa, width='stretch', height=500, returned_objects=[])
            
def main():
    st.title("Análisis de Centros Educativos de Costa Rica")

    # Cargar datos de la aplicación
    cantones_gdf, centros_gdf = cargar_datos()

    if cantones_gdf is None or centros_gdf is None:
        st.error("No se lograron cargar los datos")
        return
    
    st.sidebar.title("Filtros de datos")
    
    # Filtros de datos
    if 'PROVINCIA' in centros_gdf.columns:
        centros_gdf['PROVINCIA'] = centros_gdf['PROVINCIA'].fillna('').astype(str)
        lista_provincias = ['Todas'] + sorted([p for p in centros_gdf['PROVINCIA'].unique() if p.strip()])
    else:
        lista_provincias = ['Todas']
    
    # Filtros de cantones
    if 'PROVINCIA' in cantones_gdf.columns:
        cantones_gdf['PROVINCIA'] = cantones_gdf['PROVINCIA'].fillna('').astype(str)
    
    provincia_seleccionada = st.sidebar.selectbox("Provincia:", lista_provincias)
    tipo_institucion = st.sidebar.selectbox("Tipo de institución:", ['Todos', 'PÚBLICO', 'PRIVADO'])
    
    # Filtrar centros educativos
    if provincia_seleccionada != 'Todas':
        centros_educativos_filtrados = centros_gdf[centros_gdf['PROVINCIA'] == provincia_seleccionada]
        provincia_match = next(
            (p for p in cantones_gdf['PROVINCIA'].unique() 
             if p == provincia_seleccionada or normalizar_texto(p) == normalizar_texto(provincia_seleccionada)), 
            None
        )
        cantones_filtrados = cantones_gdf[cantones_gdf['PROVINCIA'] == provincia_match] if provincia_match else cantones_gdf.head(0)
    else:
        cantones_filtrados = cantones_gdf
        centros_educativos_filtrados = centros_gdf
    
    # Filtrar centros educativos por tipo de institución
    if tipo_institucion != 'Todos':
        centros_educativos_filtrados = centros_educativos_filtrados[
            centros_educativos_filtrados['TIPO_INSTI'] == tipo_institucion
        ]
    
    # Estadísticas de centros educativos
    if provincia_seleccionada != 'Todas' or tipo_institucion != 'Todos':
        total = len(centros_educativos_filtrados)
        publicos = len(centros_educativos_filtrados[centros_educativos_filtrados['TIPO_INSTI'] == 'PÚBLICO'])
        privados = len(centros_educativos_filtrados[centros_educativos_filtrados['TIPO_INSTI'] == 'PRIVADO'])
    else:
        total = len(centros_gdf)
        publicos = len(centros_gdf[centros_gdf['TIPO_INSTI'] == 'PÚBLICO'])
        privados = len(centros_gdf[centros_gdf['TIPO_INSTI'] == 'PRIVADO'])

    # Sidebar con estadísticas
    st.sidebar.markdown("---")
    st.sidebar.title("Estadísticas")
    st.sidebar.metric("Total de Centros Educativos", total)
    st.sidebar.metric("Centros Educativos Públicos", publicos)
    st.sidebar.metric("Centros Educativos Privados", privados)
    
    # Pestañas principales de la aplicación
    pestanas_tabla, pestanas_graficos, pestanas_mapa, pestanas_busqueda = st.tabs([
        "📊 Tabla",
        "📈 Gráfico",
        "🗺️ Mapa",
        "🔍 Búsqueda"
    ])
    
    with pestanas_tabla:
        fragmento_tabla(centros_educativos_filtrados, provincia_seleccionada)
    
    with pestanas_graficos:
        fragmento_graficos(cantones_filtrados)
    
    with pestanas_mapa:
        fragmento_mapa(cantones_filtrados, centros_educativos_filtrados, tipo_institucion)
    
    with pestanas_busqueda:
        fragmento_busqueda(centros_gdf)

if __name__ == "__main__":
    main()