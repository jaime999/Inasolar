from dash import Dash, html, dcc
import dash
import dash_bootstrap_components as dbc
import datetime
import webbrowser
import logging
from importlib import reload


# Funciones para iniciar Dash
# ---------------------------------------------------------------
reload(logging)
app = Dash(__name__, external_stylesheets=[
           dbc.themes.BOOTSTRAP, 'https://use.fontawesome.com/releases/v6.3.0/css/all.css'], use_pages=True)
app.title = 'Zona Privada'

# FUNCIONES
# ---------------------------------------------------------------
def createImg(src, title):
    return html.Img(src=src,
             alt=title,
             title=title)

# HTML
# ---------------------------------------------------------------
header = dbc.Row([
    dbc.Col(
        html.A(
            createImg(r'assets/logoInasolar.png', 'Inasolar Project'),            
            href='https://inasolar.webs.upv.es/'
        )
    ),
    dbc.Col(
        dbc.Row([
            dbc.Col(
                html.A(
                    createImg(r'assets/logoGeder.jpg', 'Geder Group'),
                    href='https://geder.es/'
                ), width=4
            ),
            dbc.Col(
                html.A(
                    createImg(r'assets/logoUpv.png', 'Universitat Politècnica de València'),
                    href='http://www.upv.es/'
                ), width=8
            ),
        ], align='center')
    )
], class_name='app-header', align='center')

contactText = f"""{datetime.date.today().year} | Equipo INASOLAR - INASOLAR Team\n
Contacto: guieses@die.upv.es - carrolbl@die.upv.es\n
Universitat Politècnica de València\n
This result is part of the Project TED2021-130464B-I00 (INASOLAR), funded by\n\n"""

logosImg = createImg(r'assets/logosProyecto.png', 'MICIN, NextGenerationUE, PRTR, AEI')

footer = dbc.Card(
    dbc.Row([
        dbc.Col(
            dbc.CardBody(
                [contactText, logosImg]),
            width=6
        )
    ], justify='center'), color='#226597', class_name='mt-3 footer'
)

app.layout = dbc.Container([
    header,
    dash.page_container,
    footer,
    dcc.Location(id='url', refresh=False)
], className='py-3')


# Abrir el fichero en la siguiente URL
# ---------------------------------------------------------------
webbrowser.open("http://127.0.0.1:8050/private", new=0, autoraise=True)
if __name__ == '__main__':
    app.run_server(debug=True, use_reloader=False, dev_tools_props_check=False)
