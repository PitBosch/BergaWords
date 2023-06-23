import pandas as pd
import plotly.express as px
import json
from statistics import mode
with open("data/BergamoGiusto.geojson") as f:
    paesi = json.load(f)
comuni=pd.read_csv("data/ComuniFinal.csv")

file="https://docs.google.com/spreadsheets/d/166me1IufiXYAHhRL6sgrXJxJTE1fVXQ-RegqU1LqEFY/export?format=csv"
i=1
SHEET_ID = '166me1IufiXYAHhRL6sgrXJxJTE1fVXQ-RegqU1LqEFY'
SHEET_NAME = 'Risposte_del_modulo_'+f'{i}'

url = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}'
df = pd.read_csv(url)
new=comuni.merge(df, left_on='Comune', right_on='Di che paese sei?', how='outer')
final=new.groupby('Comune')[new.columns[3]].agg(lambda x: mode(x)).reset_index()
final=final.fillna("Nessun Dato")

fig = px.choropleth_mapbox(final, geojson=paesi, locations="Comune", color=final.columns[1], featureidkey="properties.name", 
                           mapbox_style="carto-positron",
                           color_discrete_map={
                "Nessun Dato": "grey"},center={'lat':45.68768, 'lon':9.80})
nome=final.columns[1][10:-1]
fig.write_html('pages/'+final.columns[1][10:-1]+".html", full_html=True)
fig.write_json('static/plotly/'+final.columns[1][10:-1]+".json")