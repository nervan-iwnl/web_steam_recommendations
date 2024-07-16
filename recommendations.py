import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
import sqlite3
from datetime import datetime
from db import DATABASE_NAME, insert_user_recommendations, get_user_recommendations

def fetch_data_from_db():
    conn = sqlite3.connect(DATABASE_NAME)
    query = "SELECT * FROM games WHERE parsed_successfully = 1 and type='game'"
    data = pd.read_sql(query, conn)
    conn.close()
    return data

def prepare_data(data):
    data['combined_features'] = data.apply(lambda row: ' '.join([
        row['genres'], row['developers'], row['categories'],
        row['detailed_description'], row['about_the_game'], row['short_description']
    ]), axis=1)
    return data

def train_model(data):
    tfidf = TfidfVectorizer(stop_words='english')
    tfidf_matrix = tfidf.fit_transform(data['combined_features'])
    cosine_sim = linear_kernel(tfidf_matrix, tfidf_matrix)
    return cosine_sim, tfidf

def get_recommendations(user_game_ids, data, cosine_sim, tfidf, start_idx=0, count=100):
    indices = pd.Series(data.index, index=data['appid']).drop_duplicates()
    idx_list = [indices[appid] for appid in user_game_ids if appid in indices]

    sim_scores = pd.Series([0]*len(data))
    for idx in idx_list:
        sim_scores += pd.Series(cosine_sim[idx])

    sim_scores = sim_scores.sort_values(ascending=False)

    recommendations = data.iloc[sim_scores.index]
    recommendations = recommendations[~recommendations['appid'].isin(user_game_ids)]
    recommendations = recommendations[recommendations['release_date'] <= datetime.now().strftime('%Y-%m-%d')]

    return recommendations.iloc[start_idx:start_idx + count]



def update_user_recommendations(user_id, user_game_ids):
    data = fetch_data_from_db()
    data = prepare_data(data)
    cosine_sim, tfidf = train_model(data)
    recommendations = get_recommendations(user_game_ids, data, cosine_sim, tfidf, count=10)
    recommendations_list = recommendations[['appid', 'name', 'short_description', 'header_image', 'store_url', 'price']].to_dict(orient='records')
    insert_user_recommendations(user_id, recommendations_list)


def get_updated_recommendations(user_id, user_game_ids, start_idx=0, count=10):
    update_user_recommendations(user_id, user_game_ids)
    return get_user_recommendations(user_id, limit=count, offset=start_idx)



data = fetch_data_from_db()
data = prepare_data(data)
cosine_sim, tfidf = train_model(data)
print('ML is ready')
