#!/usr/bin/python
# -*- coding: utf-8 -*-

import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
from datetime import datetime
import pandas as pd
from sqlalchemy import create_engine

#Подключаемся к БД
db_config = {'user': 'polina',         
             'pwd': 'polina', 
             'host': 'localhost',       
             'port': 5432,              
             'db': 'zen'}             
    
connection_string = 'postgresql://{}:{}@{}:{}/{}'.format(db_config['user'],
	                                                     db_config['pwd'],
													     db_config['host'],
														 db_config['port'],
													     db_config['db'])
engine = create_engine(connection_string)


#Получаем значения всех полей из таблиц
query_engagements = '''
            SELECT * FROM dash_engagements
            '''
dash_engagements = pd.io.sql.read_sql(query_engagements, con = engine)
dash_engagements['dt'] = pd.to_datetime(dash_engagements['dt']).dt.round('min')
        
query_visits = '''
            SELECT * FROM dash_visits
            '''
dash_visits = pd.io.sql.read_sql(query_visits, con = engine)
dash_visits['dt'] = pd.to_datetime(dash_visits['dt']).dt.round('min')


#Описание дашборда
note = '''
          Дашборд для анализа поведения пользователей Яндекс.Дзен.
          Используйте фильтры по темам карточек, возрастным группам и датам для управления дашбордом.
       '''


#Задаем лейаут
external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = dash.Dash(__name__, external_stylesheets=external_stylesheets, compress=False)
app.layout = html.Div(children=[
    #Заголовок дашборда
    html.H1(children = 'Взаимодействие пользователей с карточками Яндекс.Дзен'),
    #Вставляем описание
    html.Label(note),
    html.Br(),
    
    #Фильтры дашборда
    html.Div([
        #Фильтр тем карточек
        html.Div([
            html.Label('Темы карточек'),
            dcc.Dropdown(
                options = [{'label':x, 'value':x} for x in dash_visits['item_topic'].unique()],
                value = dash_visits['item_topic'].unique().tolist(),
                multi = True,
                id = 'item_topic_dropdown',
            ),
        ], className = 'seven columns'),
        #Фильтр по возрастным категориям
        html.Div([
            html.Label('Возрастные категории'),
            dcc.Dropdown(
                options = [{'label':x, 'value':x} for x in dash_engagements['age_segment'].unique()],
                value = dash_engagements['age_segment'].unique().tolist(),
                multi = True,
                id = 'age_dropdown',
            ),           
        ], className = 'four columns'),
        #Фильтр по дате
        html.Div([
            html.Label('Выбор даты и времени'),
            dcc.DatePickerRange(
                start_date = dash_visits['dt'].min(),
                end_date = dash_visits['dt'].max(),
                display_format = 'YYYY-MM-DD',
                id = 'dt_selector',
            ),
        ], className = 'four columns'),   
    ], className = 'row'),
    html.Br(),

    #Шаблоны Графиков
    html.Div([
        #График истории событий по темам карточек
        html.Div([
            html.Label('История событий по темам карточек'),
            dcc.Graph(style = {'height': '50vw'}, 
                      id = 'history_absolute_visits'),
        ], className = 'six columns'),
        #График разбивки событий по темам источников
        html.Div([
            html.Label('События по темам источников'),
            dcc.Graph(style = {'height': '25vw'}, 
                      id = 'pie_visits'),
        ], className = 'six columns'),
        #График средней глубины взаимодействия
        html.Div([
            html.Label('Глубина взаимодействия'),
            dcc.Graph(style = {'height': '25vw'}, 
                      id = 'engagement_graph'),
        ], className = 'six columns'),
])])

#Описываем логику дашборда
@app.callback(
    [Output('history_absolute_visits', 'figure'),
     Output('pie_visits', 'figure'),
     Output('engagement_graph', 'figure'),
    ],   
    [Input('age_dropdown', 'value'),
     Input('item_topic_dropdown', 'value'),
     Input('dt_selector', 'start_date'),
     Input('dt_selector', 'end_date')])
     

def update_figures(selected_ages, selected_item_topics, start_date, end_date):
    #Применяем фильтрацию
    dash_visits_filtered = dash_visits.query('item_topic.isin(@selected_item_topics) and \
                                                dt >= @start_date and dt <= @end_date \
                                                and age_segment.isin(@selected_ages)')
        
    dash_engagements_filtered = dash_engagements.query('item_topic.isin(@selected_item_topics) and \
                                                    dt >= @start_date and dt <= @end_date \
                                                    and age_segment.isin(@selected_ages)')
                                                    
    #Группируем данные
    visits_by_item_topic = dash_visits_filtered.groupby(['item_topic', 'dt']).agg({'visits':'sum'}).reset_index()
    
    source_topic = dash_visits_filtered.groupby(['source_topic']).agg({'visits':'sum'}).reset_index()
    
    engagements_by_event = dash_engagements_filtered.groupby('event').agg({'unique_users':'mean'}).reset_index()
    engagements_by_event = engagements_by_event.sort_values('unique_users', ascending = False)
    
    #График истории событий по темам карточек
    data_by_visits = []
    for item in visits_by_item_topic['item_topic'].unique():
        data_by_visits += [go.Scatter(x = visits_by_item_topic.query('item_topic == @item')['dt'],
                                        y = visits_by_item_topic.query('item_topic == @item')['visits'],
                                        mode = 'lines',
                                        stackgroup = 'one',
                                        name = item)]
                                        
    #График разбивки событий по темам источников
    data_by_source = [go.Pie(labels = source_topic['source_topic'], values = source_topic['visits'], name = 'source_topics')]
    
    #График средней глубины взаимодействия
    data_by_engagements = [go.Bar(x = engagements_by_event['event'], y = engagements_by_event['unique_users'])]
        
    #формируем результат для отображения
    return(
            {'data':data_by_visits,
            'layout': go.Layout(xaxis = {'title': 'дата'},
                                yaxis = {'title': 'количество событий'})},
            {'data': data_by_source,
             'layout': go.Layout()},           
            {'data': data_by_engagements,
             'layout': go.Layout(xaxis = {'title': 'событие'}, yaxis = {'title': 'количество взаимодействий'})})


if __name__ == '__main__':
    app.run_server(debug=True)















