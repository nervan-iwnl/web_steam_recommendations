import os
import threading
from flask import Flask, redirect, url_for, session, render_template, jsonify, request
from flask_openid import OpenID
import requests
from dotenv import load_dotenv
from recommendations import get_recommendations, data, cosine_sim, tfidf
from db import DATABASE_NAME, sqlite3, add_game_details, get_user_recommendations, insert_user_recommendations, rec_update, update_db
from datetime import datetime
import pycountry

load_dotenv()

STEAM_API_KEY = os.getenv('STEAM_API_KEY')
SECRET_KEY = os.urandom(24)
STEAM_OPENID_URL = "https://steamcommunity.com/openid"

app = Flask(__name__)
app.secret_key = SECRET_KEY
oid = OpenID(app, safe_roots=[])

@app.route('/')
def index():
    steam_id = session.get('steam_id')
    steam_profile = None
    if steam_id:
        profile_url = f'http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/?key={STEAM_API_KEY}&steamids={steam_id}'
        response = requests.get(profile_url)
        if response.status_code == 200:
            data = response.json()
            player_data = data.get('response', {}).get('players', [])[0]
            nickname = player_data.get('personaname', 'Unknown')
            country = player_data.get('loccountrycode', 'Unknown')
            avatar = player_data.get('avatarmedium', '')
            try:
                country = pycountry.countries.get(alpha_2=country).name
            except Exception:
                country = "Unknown"
            created_date = datetime.fromtimestamp(player_data.get('timecreated', 'Unknown'))
        else:
            nickname = 'Unknown'
            avatar = ''
            country = 'Unknown'
            created_date = 'Unknown'
        steam_profile = {
            'avatar': avatar,
            'nickname': nickname,
            'region': country,
            'created_date': created_date
        }
    return render_template('index.html', steam_id=steam_id, steam_profile=steam_profile)    
@app.route('/login')
@oid.loginhandler
def login():
    if 'steam_id' in session:
        return redirect(url_for('get_games'))
    return oid.try_login(STEAM_OPENID_URL)

@oid.after_login
def create_or_login(resp):
    steam_id = resp.identity_url.split('/')[-1]
    session['steam_id'] = steam_id
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/get_games')
def get_games():
    steam_id = session.get('steam_id')
    if not steam_id:
        return redirect(url_for('index'))

    url = f'http://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/?key={STEAM_API_KEY}&steamid={steam_id}&format=json&include_appinfo=true'
    response = requests.get(url)
    data = response.json()

    games = [game for game in data.get('response', {}).get('games', [])]
    session['games'] = [game['appid'] for game in games] 
    session['games_names'] = [game['name'] for game in games]
    return render_template('games.html', games=games[:20])


@app.route('/load_more_games')
def load_more_games():
    offset = request.args.get('offset', type=int)
    if offset is None:
        offset = 0

    return jsonify(session['games_names'][offset:min(offset + 20, len(session['games']))])



@app.route('/recommend')
def recommend():
    steam_id = session.get('steam_id')
    game_ids = session.get('games', [])
    if not game_ids:
        return redirect(url_for('index'))

    recommendations = get_recommendations(game_ids, data, cosine_sim, tfidf)
    recommendations = recommendations.to_dict('records')

    recommendation_ids = [rec['appid'] for rec in recommendations]
    insert_user_recommendations(steam_id, recommendation_ids)

    initial_recommendations = recommendation_ids[:10]
    initial_recommendations_details = add_game_details(initial_recommendations)

    return render_template('recommendation.html', recommendations=initial_recommendations_details)

@app.route('/load_more_recommendations')
def load_more_recommendations():
    steam_id = session.get('steam_id')
    offset = request.args.get('offset', 0, type=int)

    additional_recommendations = get_user_recommendations(steam_id, limit=10, offset=offset)
    additional_recommendations_details = add_game_details(additional_recommendations)

    return jsonify(additional_recommendations_details)


if __name__ == '__main__':
    #update_db(1000, True) # Use to create database 
    update_thread = threading.Thread(target=rec_update)
    update_thread.daemon = True
    update_thread.start()
    app.run(debug=True)
