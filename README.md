# Proyecto Final: Aplicación interactiva con Streamlit para el análisis de Centros Educativos de Costa Rica

El siguiente código corresponde a una aplicación desarrollada con Streamlit para el análisis de los centros educativos de Costa Rica. La aplicación permite explorar, visualizar y analizar la distribución geográfica y características de las instituciones educativas del país mediante una interfaz interactiva que incluye múltiples componentes:

* Tablas: Lista de centros educativos de Costa Rica.
* Gráficos: Visualizaciones comparativas de densidad de centros educativos y densidad poblacional por cantón.
* Mapas: Distribución geográfica con capas de densidad y marcadores por tipo de institución.
* Filtros: Controles laterales para filtrar por provincia y tipo de institución.
* Búsqueda: Herramienta de localización de centros educativos por ubicación geográfica o por nombre.

## 1. Descripción general del conjunto de datos utilizados

### 1.1. Centros Educativos de Costa Rica

Este conjunto de datos reuné información sobre los centros educativos de Costa Rica, tanto públicos como privados. Los centros educativos comprenden instituciones de diferentes niveles y modalidades del sistema educativo costarricense como preescolar, primaria, secundaria y técnica, así como centros de educación especial y educación para personas jóvenes y adultas. El propósito de este conjunto de datos es ofrecer una visión integral del panorama educativo nacional, permitiendo conocer la distribución territorial, las características institucionales y la oferta educativa existente en el país.

La georreferenciación de cada centro es realizada por el equipo técnico del [**SIGMEP**](https://sigmep.maps.arcgis.com/home/index.html) (Sistema de Información Geográfica del Ministerio de Educación Pública), mientras que la información general es proporcionada por el Departamento de Análisis Estadístico y la Dirección de Centros Privados del MEP. 

Los datos están disponibles a través del servicio web de **ArcGIS Server**, mediante el servicio publicado [**CE_Publicos_CR**](https://services1.arcgis.com/aWQmxJWy7lM2Qqmo/arcgis/rest/services/CE_Publicos_CR/FeatureServer). Este servicio contiene dos capas principales:

* Centros educativos públicos: Administrados por el Estado costarricense bajo la rectoría del Ministerio de Educación Pública (MEP).
* Centros educativos privados: Gestionados por entidades privadas, pero supervisados y autorizados por el MEP.

Con el objetivo de facilitar el análisis estadístico y geográfico, ambas capas fueron consolidadas en un único archivo CSV, dado que comparten la misma estructura y columnas de información.

### 1.2 Cantones de Costa Rica
El conjunto de datos contiene las geometrías de los 82 cantones de Costa Rica. Este archivo permite realizar operaciones espaciales para determinar a qué cantón pertenece cada centro educativo y calcular métricas de densidad por área. Los datos fueron obtenidos del [Instituto Geográfico Nacional (IGN)](https://www.ign.gob.cr/).

### 1.3 Población y vivienda por cantón
El conjunto de datos contiene datos demográficos por cantón, incluyendo la población total. Estos datos permiten calcular indicadores como la densidad poblacional y el número de centros educativos por cada 10,000 habitantes. Los datos fueron obtenidos del [Instituto Nacional de Estadística y Censos (INEC)](https://inec.cr).

## 2. Descripción de sus principales variables: Centros Educativos de Costa Rica

El conjunto de datos de centros educativos contiene 15 variables, la mayoría recopiladas para todos los centros. En la tabla siguiente se presentan cada una de las variables, junto con su descripción, tipo y categoría.

| **Variable** | **Descripción** | **Tipo de variable** | **Categoría** |
|--------------|----------------------------|-----------------------|---------------|
| CODSABER | Código único asignado por el [Sistema de Administración Básica de la Educación y sus Recursos (SABER)](https://www.mep.go.cr/saber) del MEP. Identifica oficialmente cada centro educativo dentro del sistema nacional. | Categórica | Identificador |
| CODPRES | Código de identificación institucional del centro educativo, generalmente asignado por el MEP para fines administrativos o presupuestarios. | Categórica | Identificador |
| CENTRO_EDU | Nombre oficial del centro educativo según los registros del MEP. | Categórica | Información del centro educativo |
| TIPO_INSTI | Clasificación del centro educativo según su régimen administrativo o tipo de gestión (pública o privada). | Categórica | Información del centro educativo |
| ESTADO | Estado actual del centro educativo (activo o cerrado). | Categórica | Información del centro educativo |
| CORREO | Dirección de correo electrónico institucional o de contacto. | Categórica | Información del centro educativo |
| REGIONAL | Nombre de la dirección regional de educación a la que pertenece el centro. | Categórica | Ubicación administrativa |
| CIRCUITO | Nombre del circuito educativo dentro de la dirección regional. | Categórica | Ubicación administrativa |
| PROVINCIA | Provincia en la que se ubica el centro educativo. | Categórica | Ubicación administrativa |
| CANTON | Cantón al que pertenece el centro educativo. | Categórica | Ubicación administrativa |
| DISTRITO | Distrito dentro del cantón donde está ubicado el centro educativo. | Categórica | Ubicación administrativa |
| POBLADO | Localidad o poblado donde se encuentra el centro educativo. | Categórica | Ubicación administrativa |
| DIRECCION | Dirección física completa, con puntos de referencia o calles. | Categórica | Georreferenciación |
| LATITUD | Coordenada geográfica de latitud. | Numérica | Georreferenciación |
| LONGITUD | Coordenada geográfica de longitud. | Numérica | Georreferenciación |