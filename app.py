from flask import Flask, render_template
from flask import request, escape
import functools
from flask import (
    Blueprint, flash, g, redirect, render_template, request, session, url_for
)
from werkzeug.security import check_password_hash, generate_password_hash
import os
import plotly
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import requests
from datetime import datetime, date
import json
import plotly.express as px

app = Flask(__name__)
app.config['API'] = os.environ.get('API')
app.config['PASSWORD'] = os.environ.get('PASSWORD')
app.secret_key = os.environ.get('SECRET')
port = int(os.environ.get("PORT", 5000))


@app.before_request
def set_roldid_session():
    if 'roleid' in request.args:
        session['roleid'] = request.args['roleid']

@app.route("/")
def index():
    return (
        """<form action="/dashboard" method="post">
                <input type="password" name="password">
                <input type="submit" value="Go">
              </form>"""
        )

@app.route("/<roleid>", methods =['POST', 'GET'])
def login(roleid):
    password = str(escape(request.args.get("password", "")))
    for document in os.listdir('./templates/'):
        if document.endswith('figure.html'):
            os.remove('./templates/' + document)
    return (
        """<form action="/dashboard" method="post">
                <input type="password" name="password">
                <input type="submit" value="Go">
              </form>"""
        )

@app.route("/dashboard", methods =['POST', 'GET'])
def launch():
    password = request.form['password']
    roleid = session['roleid']
    if not check_password_hash(app.config['PASSWORD'], password):
        return redirect("/?roleid=" + roleid)
    
    def apiq(roleid, archived = False):
        if archived is False:
            posting_id = 'posting_id'
        else:
            posting_id = 'archived_posting_id'
            
        raw = requests.get(f'https://api.lever.co/v1/opportunities?{posting_id}={roleid}&limit=100', auth=(app.config['API'], ''))
        raw_json = raw.json()
        df = pd.DataFrame(raw_json)

        try:
            y = raw_json['next']
        except:
            pass
        
        df2 = pd.DataFrame()
        try:
            if y in df.values:
                raw2 = requests.get(f'https://api.lever.co/v1/opportunities?{posting_id}={roleid}&limit=100&offset={y}', auth=(app.config['API'], ''))
                raw2_json = raw2.json()
                df2 = pd.DataFrame(raw2_json)
                try:
                    n = raw2_json['next']
                    while n in df2.values:
                        raw = requests.get(f'https://api.lever.co/v1/opportunities?{posting_id}={roleid}&limit=100&offset={n}', auth=(app.config['API'], ''))
                        raw2_json = raw.json()
                        try:
                            n = raw2_json['next']
                        except:
                            df3 = pd.DataFrame(raw2_json)
                            df2 = pd.concat([df2, df3])
                            break
                        df3 = pd.DataFrame(raw2_json)
                        df2 = pd.concat([df2, df3])
                except:
                    pass
        except:
            pass
        df = pd.concat([df, df2])
        return df

    df = apiq(roleid, archived = False)
    df2 = apiq(roleid, archived = True)

    data_list = df["data"].tolist()
    df_final = pd.DataFrame(data_list)
    try:
        df_final.drop(["name", "contact", "headline", "confidentiality", "location", "phones", "emails", "links", "archived", "stageChanges", "origin", "owner", "followers", "applications", "urls", "isAnonymized", "dataProtection", "contact"], axis = 1, inplace = True) 
    except:
        pass

    data2_list = df2["data"].tolist()
    df2_final = pd.DataFrame(data2_list)

    total_active = len(df_final.index)
    total_inactive = len(df2_final.index)


    def convertTime(t):
        from datetime import datetime, date
        t = int(t)
        return datetime.fromtimestamp(t)
    try:
        df_final["createdAt"]= df_final["createdAt"]/1000
        df_final["createdAt"] = df_final["createdAt"].apply(convertTime)
        df_final.set_index("createdAt", inplace = True)
        total_today = df_final.loc[pd.to_datetime('today').strftime('%Y-%m-%d')]
        total_today = len(total_today)
    except:
        total_today = 0
        pass
    
    total = total_active + total_inactive


    df_final.reset_index(inplace = True)

    try:
        df2_final["createdAt"]= df2_final["createdAt"]/1000
        df2_final["createdAt"] = df2_final["createdAt"].apply(convertTime)
    except:
        pass

    df_final = pd.concat([df_final, df2_final])
    
    try:
        df_final.drop(["name", "contact", "headline", "confidentiality", "location", "phones", "emails", "links", "archived", "stageChanges", "origin", "owner", "followers", "applications", "urls", "isAnonymized", "dataProtection", "contact"], axis = 1, inplace = True) 
    except:
        pass

    titledat = requests.get(f'https://api.lever.co/v1/postings/{roleid}/apply', auth=(app.config['API'], ''))
    titledat = titledat.json()

    
    fig = go.Figure()
    
    fig = make_subplots(rows=2, cols=2, subplot_titles=("Applications by Source","Applications over Time"))

    fig.add_trace(go.Indicator(
        mode = "number",
        value = total_today,
        title = {"text": "Total Applications Today"},
        domain = {'row': 1, 'column': 0}))

    fig.add_trace(go.Indicator(
        mode = "number",
        value = total_active,
        title = {"text": "Total in Pipeline"},
        domain = {'row': 1, 'column': 1}))

    fig.add_trace(go.Indicator(
        mode = "number",
        value = total,
        title = {"text": "Grand Total (archived+active)"},
        domain = {'row': 1, 'column': 2}))

    fig.update_traces(title_font_size = 15, number_font_size = 30, selector = dict(type = 'indicator'))
    
    try:
        fig.add_trace(go.Histogram(
            x = df_final.createdAt,
            name = "Applicants",
            marker_color='#109618'),
            row = 1, col = 2)
    except:
        pass

    try:
        fig.add_trace(go.Bar(
            y = df_final.sources.value_counts().tolist(),
            x = list(map(', '.join, (df_final.sources.value_counts().index).tolist())),
            name = "sources",
            showlegend = False,
            marker_color = px.colors.qualitative.Plotly),
            row = 1, col = 1)
    except:
        pass
    
    try:
        fig.update_layout(
            grid = {'rows': 2, 'columns': 3, 'pattern': "independent"},
            title_text = str(titledat['data']['text']),
            title_x = 0.5,
            template = {'data' : {'indicator': [{
                'mode' : "number"}]
                                 }})
    except:
            fig.update_layout(
                grid = {'rows': 2, 'columns': 3, 'pattern': "independent"},
                title_x = 0.5,
                template = {'data' : {'indicator': [{
                    'mode' : "number"}]
                                     }})
            
    fig = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
    return render_template('page.html', fig=fig)
    

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=port, debug=False)
