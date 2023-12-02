import pandas as pd
import plotly.express as px
import json
from statistics import mode
import openpyxl
with open("data/BergamoGiusto.geojson") as f:
    paesi = json.load(f)
comuni=pd.read_csv("data/ComuniFinal.csv")




#read the first sheet 
# loop on all sheets of comesidice.xlsx
for i in range(1, 30):
    SHEET_NAME = 'Risposte del modulo '+f'{i}'
    df = pd.read_excel('comesidice.xlsx', sheet_name=SHEET_NAME)
    new=comuni.merge(df, left_on='Comune', right_on='Di che paese sei?', how='outer')
    final=new.groupby('Comune')[new.columns[3]].agg(lambda x: mode(x)).reset_index()
    final=final.fillna("Nessun Dato")
    fig = px.choropleth_mapbox(final, geojson=paesi, locations="Comune", color=final.columns[1], featureidkey="properties.name", 
                           mapbox_style="carto-positron",
                           color_discrete_map={
                "Nessun Dato": "grey"},center={'lat':45.68768, 'lon':9.80})
    nome=final.columns[1][10:-1]
    fig.write_json('static/plotly/'+final.columns[1][10:-1]+".json")