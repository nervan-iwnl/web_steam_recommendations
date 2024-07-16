import sqlite3
import requests
import time
import json
from datetime import datetime
import schedule
import time

DATABASE_NAME = 'steam_games.db'

def get_all_games():
    url = "https://api.steampowered.com/ISteamApps/GetAppList/v2/"
    response = requests.get(url)
    data = response.json()
    return data['applist']['apps']

def get_game_details(appid):
    url = f"https://store.steampowered.com/api/appdetails?appids={appid}"
    response = requests.get(url)
    data = response.json()
    if data and data[str(appid)]['success']:
        if str(appid) in data and 'data' in data[str(appid)]:
            details = data[str(appid)]['data']
        else:
            details = {}
        return {
            'appid': appid,
            'type': details.get('type', ''),
            'name': details.get('name', ''),
            'required_age': details.get('required_age', 0),
            'is_free': details.get('is_free', False),
            'detailed_description': details.get('detailed_description', ''),
            'about_the_game': details.get('about_the_game', ''),
            'short_description': details.get('short_description', ''),
            'supported_languages': details.get('supported_languages', ''),
            'header_image': details.get('header_image', ''),
            'capsule_image': details.get('capsule_image', ''),
            'capsule_imagev5': details.get('capsule_imagev5', ''),
            'website': details.get('website', ''),
            'pc_requirements': dict(details.get('pc_requirements', {})).get('minimum', 'Not available'),
            'mac_requirements': dict(details.get('mac_requirements', {})).get('minimum', 'Not available'),
            'linux_requirements': dict(details.get('linux_requirements', {})).get('minimum', 'Not available'),
            'platforms': json.dumps(details.get('platforms', {})),
            'categories': json.dumps(details.get('categories', [])),
            'screenshots': json.dumps(details.get('screenshots', [])),
            'movies': json.dumps(details.get('movies', [])),
            'genres': json.dumps(details.get('genres', [])),
            'developers': json.dumps(details.get('developers', [])),
            'publishers': json.dumps(details.get('publishers', [])),
            'total_ratings': details.get('recommendations', {}).get('total', 0),
            'positive_ratings': details.get('recommendations', {}).get('positive', 0),
            'negative_ratings': details.get('recommendations', {}).get('negative', 0),
            'price': details.get('price_overview', {}).get('final_formatted', 'Free'),
            'release_date': details.get('release_date', {}).get('date', ''),
            'store_url': f"https://store.steampowered.com/app/{appid}"
        }
    else:
        save_failed_game(appid)
        return None

def save_failed_game(appid):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO games (appid, parsed_successfully)
        VALUES (?, 0)
    ''', (appid,))
    conn.commit()
    conn.close()

def create_database():
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS games (
        appid INTEGER PRIMARY KEY,
        type TEXT,
        name TEXT,
        required_age INTEGER,
        is_free BOOLEAN,
        detailed_description TEXT,
        about_the_game TEXT,
        short_description TEXT,
        supported_languages TEXT,
        header_image TEXT,
        capsule_image TEXT,
        capsule_imagev5 TEXT,
        website TEXT,
        pc_requirements TEXT,
        mac_requirements TEXT,
        linux_requirements TEXT,
        platforms TEXT,
        categories TEXT,
        screenshots TEXT,
        movies TEXT,
        genres TEXT,
        developers TEXT,
        publishers TEXT,
        total_ratings INTEGER,
        positive_ratings INTEGER,
        negative_ratings INTEGER,
        price TEXT,
        release_date TEXT,
        parsed_successfully BOOLEAN DEFAULT 1
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_recommendations (
        user_id TEXT PRIMARY KEY,
        recommendations TEXT
    )
    ''')

    conn.commit()
    conn.close()

def insert_game_details(game_details):
    if game_details:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        cursor.execute('''
        INSERT OR REPLACE INTO games (
            appid, type, name, required_age, is_free, detailed_description, about_the_game, short_description,
            supported_languages, header_image, capsule_image, capsule_imagev5, website, pc_requirements,
            mac_requirements, linux_requirements, platforms, categories, screenshots, movies, genres,
            developers, publishers, total_ratings, positive_ratings, negative_ratings, price, release_date, parsed_successfully
        ) VALUES (
            :appid, :type, :name, :required_age, :is_free, :detailed_description, :about_the_game, :short_description,
            :supported_languages, :header_image, :capsule_image, :capsule_imagev5, :website, :pc_requirements,
            :mac_requirements, :linux_requirements, :platforms, :categories, :screenshots, :movies, :genres,
            :developers, :publishers, :total_ratings, :positive_ratings, :negative_ratings, :price, :release_date, 1
        )
        ''', game_details)
        
        conn.commit()
        conn.close()

def insert_user_recommendations(user_id, recommendations):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
    INSERT OR REPLACE INTO user_recommendations (
        user_id, recommendations
    ) VALUES (?, ?)
    ''', (user_id, json.dumps(recommendations)))
    
    conn.commit()
    conn.close()

def get_user_recommendations(user_id, limit=10, offset=0):
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT recommendations
    FROM user_recommendations
    WHERE user_id = ?
    ''', (user_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        all_recommendations = json.loads(row[0])
        recommendations = all_recommendations[offset:offset + limit]
        
        return recommendations
    else:
        return []

def update_db(batch_size=100, limit=False):
    create_database()
    all_games = get_all_games()
    total_games = len(all_games)
    print(f"Total games retrieved: {total_games}")

    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT appid FROM games')
    existing_appids = set(row[0] for row in cursor.fetchall())
    conn.close()

    new_games = [game for game in all_games if game['appid'] not in existing_appids]
    new_games.sort(key=lambda x : x['appid'])
    new_total_games = len(new_games)
    print(f"New games to add: {new_total_games}")

    if limit:
        new_games = new_games[:batch_size]

    for game in new_games:
        appid = game['appid']
        game_details = get_game_details(appid)
        insert_game_details(game_details)
        time.sleep(1)  # Avoid hitting the API rate limit

    print("Database update complete")



def add_game_details(recommendations):
    game_details = []
    if recommendations:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        query = f"SELECT appid, name, short_description, header_image, price FROM games WHERE appid IN ({','.join('?' * len(recommendations))})"
        cursor.execute(query, recommendations)
        rows = cursor.fetchall()

        for row in rows:
            game_details.append({
                "appid": row[0],
                "name": row[1],
                "description": row[2] or "Описание отсутствует",
                "header_image": row[3] or "",
                "price": row[4] or "Цена не указана",
                "store_url": f'https://store.steampowered.com/app/{row[0]}' or "#"
            })

        conn.close()

    return game_details


def rec_update():
    def job():
        print(f"Running update_db at {datetime.now()}")
        update_db(limit=True)

    schedule.every().day.at("01:00").do(job)
    while True:
        schedule.run_pending()
        time.sleep(1)
