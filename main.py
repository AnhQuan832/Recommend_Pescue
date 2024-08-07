from flask import Flask, jsonify
from flask_restful import  Api, Resource
import pandas as pd
import numpy as np
import requests
import logging
from surprise import Dataset, Reader, KNNBasic, SVD, accuracy, similarities
from surprise.model_selection import train_test_split
import joblib
import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sklearn.decomposition import TruncatedSVD


MODEL_PATH_REC = 'model_rec.pkl'
MODEL_PATH_TAB = 'model_tab.pkl'
DATA_PATH = 'data.pkl'
DATA_ID_PRODUCT = 'data_id_prod.pkl'
DATA_ID_USER = 'data_id_user.pkl'
DATA_USER = 'data_user.pkl'

app = Flask(__name__)
api = Api(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
api_url='https://kltn-pescue-production.up.railway.app/api/v1/data/'
api_header = {'client-id' : 'PqescSU7WscLlNRvHK2Ew397vBa0b7dr','client-key': 'opIGrWw2u0WBmZHVIyDRqM6t0P2NKE1c'}
#Item-based Collaborative Filtering
sim_options = {
    'name': 'cosine',
    'user_based': False  
}

class Recommend(Resource):
    def get(self, product_id):
        similar_products = get_recommend_product(product_id)
        return similar_products


def parse_id(data):
    user_id_map = {id: idx + 1 for idx, id in enumerate(data['userId'].unique())}
    product_id_map = {id: idx + 1 for idx, id in enumerate(data['productId'].unique())}
    data.loc[:, 'productId_mapped'] = data['productId'].map(product_id_map)
    data.loc[:, 'userId_mapped'] = data['userId'].map(user_id_map)
    rating = data[['userId_mapped', 'productId_mapped','score']]
    return data,user_id_map, product_id_map

def train_model(num_recommendations= 40):
    rating_raw = pd.DataFrame(get_products())

   #
    # reader = Reader(rating_scale=(1, 5))  
    # data = Dataset.load_from_df(rating[['userId_mapped', 'productId_mapped', 'score']], reader)
    
    # trainset, testset = train_test_split(data, test_size=0.2)
    # model = KNNBasic(sim_options=sim_options)
    # model.fit(trainset)
    # predictions = model.test(testset)
    # sim_matrix = model.compute_similarities()
    # inner_id = model.trainset.to_inner_iid(product_id_mapped)
    # neighbors = model.get_neighbors(inner_id, k=num_recommendations)

    # neighbors = [model.trainset.to_raw_iid(inner_id) for inner_id in neighbors]
    # app.logger.info(neighbors)
    #
    
    rating = rating_raw.pivot_table(values='score', index='productId', columns='userId', fill_value=0)
    rating_matrix = rating
    print(f"Rating shape: {rating_matrix.shape}")

    SVD = TruncatedSVD(n_components=10)
    decomposed_matrix = SVD.fit_transform(rating_matrix)
    print(f"Decomposed shape: {decomposed_matrix.shape}")
    correlation_matrix = np.corrcoef(decomposed_matrix)

    return correlation_matrix,rating_matrix

def get_recommend_product(product_id):
    try:
        # correlation_matrix, rating_matrix, product_id_map,user_id_map, rating_raw = load_or_train_model()
        # viewed_product_raw = pd.DataFrame(get_view_by_product(product_id))
        # viewed_product_raw = viewed_product_raw.dropna()
        # if viewed_product_raw.empty:
        #     app.logger.info("Empty data", viewed_product_raw.empty)
        #     return []
        # viewed_product_raw = viewed_product_raw.rename(columns={'viewerId': 'userId', 'objectId': 'productId'})
    
        # viewed_product_raw.loc[:, 'userId_mapped'] = viewed_product_raw['userId'].map(user_id_map)
        # viewed_product_raw.loc[:, 'productId_mapped'] = viewed_product_raw['productId'].map(product_id_map)
        
        # viewed_product = viewed_product_raw[['userId_mapped']]
        # viewed_product = viewed_product.dropna(subset=['userId_mapped'])
        # users_who_viewed = set(viewed_product['userId_mapped'])
        # user_list = list(users_who_viewed)
        # user_list = [int(user_id) for user_id in user_list]
        # product_id_mapped = product_id_map[product_id]

        # existing_user_ids = rating_matrix.index.tolist()

        # filtered_user_list = [user_id for user_id in user_list if user_id in existing_user_ids]

        # filtered_indices = [existing_user_ids.index(user_id) for user_id in filtered_user_list]
        # filtered_correlation_matrix = correlation_matrix[filtered_indices, :]

        # user_similarities = filtered_correlation_matrix[product_id_mapped]

        # top_product_indices = np.argsort(user_similarities)[-5:]

        #
        # viewed_product_raw = pd.DataFrame(get_view_by_product(product_id))
        # viewed_product_raw = viewed_product_raw.rename(columns={'viewerId': 'userId', 'objectId': 'productId'})
        # user_list = viewed_product_raw['userId'].unique()

        # print(f"Rating shape: {rating}")
        # filtered_rating_matrix = rating_matrix.loc[rating_matrix['userId'].isin(user_list)]
        # print(f"Filtered rating shape: {filtered_rating_matrix}")

        correlation_matrix, rating_matrix = load_or_train_model()
        #

        product_names = list(rating_matrix.index)
        product_ID = product_names.index(product_id)
        correlation_product_ID = correlation_matrix[product_ID]
        print(f"Correlation shape: {correlation_product_ID.shape}")
        corr_score = 0.9
        Recommend = []
        while len(Recommend) < 5:
            Recommend = list(rating_matrix.index[correlation_product_ID > corr_score])
            Recommend.remove(product_id)
            corr_score -= 0.05

        print(f"Corr_score: {corr_score}")
        # similar_products = similar_products.drop_duplicates(subset=['productId'])
        # similar_products_json = similar_products[['productId','score']]
        # recommend = list(rating_matrix.index[top_product_indices])
        # similar_products = pd.DataFrame(recommend, columns=['productId_mapped']).merge(rating_raw, left_on='productId_mapped', right_on='productId_mapped')

        # similar_products = similar_products.drop_duplicates(subset=['productId'])
        # print(f"similar_products: {similar_products}")
        # similar_products_json = similar_products['productId'].tolist()
        response = {'listProduct': Recommend[0:5]}

        return response
    except Exception as e:
        return {"message": "Error: " + str(e)}

def load_or_train_model():
    if os.path.exists(MODEL_PATH_REC):
        model = joblib.load(MODEL_PATH_REC)
        rating_matrix = joblib.load(DATA_PATH)
        app.logger.info("Model loaded")
    else:
        return over_ride_model()
    return model, rating_matrix

def over_ride_model():
    model, rating_matrix = train_model()
    joblib.dump(model, MODEL_PATH_REC)
    joblib.dump(rating_matrix, DATA_PATH)
    app.logger.info("Model trained")
    return model, rating_matrix

def get_products():
    try:
        response = requests.get(f'{api_url}rating',headers=api_header)
        if response.status_code == 200:
            res = response.json()
            if res['meta']['statusCode'] == '0_2_s':
                return res['data']['ratingData']
    except Exception as e:
        return {"message": "Error: " + str(e)}

def get_view_by_product(product_id):
    try:
        response = requests.get(f'{api_url}views-audit-log/{product_id}', headers=api_header)
        if response.status_code == 200:
            res = response.json()
            if res['meta']['statusCode'] == '0_2_s':
                return res['data']['views']
    except Exception as e:
        return {"message": "Error: " + str(e)}
    
def get_invoices():
    try:
        response = requests.get(f'{api_url}invoice', headers=api_header)
        if response.status_code == 200:
            res = response.json()
            if res['meta']['statusCode'] == '0_2_s':
                return res['data']['invoiceData']
    except Exception as e:
        return {"message": "Error: " + str(e)}
    



api.add_resource(Recommend, "/recommend-product/<product_id>")

scheduler = BackgroundScheduler()
scheduler.add_job(over_ride_model, CronTrigger(year="*", month="*", day="*", hour="1", minute="0", second="0"))
scheduler.start()

if __name__ == "__main__":
    scheduler.init_app(app)
    scheduler.start()
    app.run(debug=False)
