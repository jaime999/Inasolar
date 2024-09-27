import dash
import dash_bootstrap_components as dbc
from dash import html, dcc


# Funciones para iniciar Dash
# ---------------------------------------------------------------
dash.register_page(__name__, path='/private', title='Zona Privada')


# Funciones globales a utilizar
# ---------------------------------------------------------------
def getAppDescription(title, img, description, href):
    return dbc.Card([
        dbc.Row([
            dbc.Col(
                dbc.CardImg(
                    src=rf'assets/{img}.png',
                    className="img-fluid rounded-start",
                ),
                className="col-md-8",
            ),
            dbc.Col(
                dbc.CardBody([
                    html.H4(title, className='card-title'),
                    html.P(description),
                    dbc.Button([
                        dcc.Link('Open', href=href)], className='mt-auto home-links'
                    )
                ])
            )
        ])
    ], class_name='p-3 my-3')


# Código HTML que se encuentra en la página
# ---------------------------------------------------------------
layout = html.Div(children=[
    getAppDescription('Inasolar Graphs', 'inasolarGraphs',
                      'App for data visualization', 'web-inasolargraphs'),
    getAppDescription('Similar Days', 'similarDays',
                      'App for comparing power between dates', 'web-similardays'),
    getAppDescription('Resource Allocation', 'resourceAllocation',
                      'App for simulate the power needed in a date', 'web-resourceallocation'),
    getAppDescription('Unit Commitment', 'unitCommitment',
                      'App for predict the energy needed in the future', 'web-unitcommitment')

])
