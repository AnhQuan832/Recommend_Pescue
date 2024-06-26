from flask import Flask, jsonify
from flask_restful import  Api, Resource
import pandas as pd
import numpy as np
import requests
import logging
from surprise import Dataset, Reader, KNNBasic, SVD, accuracy
from surprise.model_selection import train_test_split
import joblib
import os


MODEL_PATH_REC = 'model_rec.pkl'
MODEL_PATH_SIM = 'model_sim.pkl'
app = Flask(__name__)
api = Api(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()
api_url='https://kltn-pescue-production.up.railway.app/api/v1/data/'
api_header = {'client-id' : 'PqescSU7WscLlNRvHK2Ew397vBa0b7dr','client-key': 'opIGrWw2u0WBmZHVIyDRqM6t0P2NKE1c'}
#Item-based Collaborative Filtering
sim_options = {
    'name': 'pearson',
    'user_based': False  
}


class Recommend(Resource):
    def get(self, product_id):
        similar_products = get_recommend_product(product_id, num_recommendations=5)
        return similar_products

class SimilarProduct(Resource):
    def get(self, product_id):
        similar_products = recommend_similar_products(product_id, num_recommendations=5)
        return similar_products
    
def generate_random_data(num_users=100, num_products=50, num_invoices=500):
    userIds = np.arange(1, num_users + 1)
    objectId = np.random.randint(1, 100, size=num_users)
    viewed_product_data = {
        'viewerId': userIds,
        'objectId': objectId
    }
    viewed_product = pd.DataFrame(viewed_product_data)

    product_ids = [f'P{i}' for i in range(1, num_products + 1)]
    category_names = np.random.choice(['Electronics', 'Clothing', 'Accessories', 'Home', 'Toys'], size=num_products)
    prices = np.round(np.random.uniform(5, 500, size=num_products), 2)
    product_data = {
        'productId': product_ids,
        'categoryName': category_names,
        'price': prices
    }
    product = pd.DataFrame(product_data)

    invoice_userIds = np.random.choice(userIds, size=num_invoices)
    invoice_product_ids = np.random.choice(product_ids, size=num_invoices)
    invoice_data = {
        'userId': invoice_userIds,
        'productId': invoice_product_ids
    }
    invoice = pd.DataFrame(invoice_data)

    return viewed_product, invoice, product

# def prepare_data():

#     products["product"] = item_enc.fit_transform(products["productId"])
#     products["category"] = category_enc.fit_transform(products["categoryName"])

#     # Build product profile
#     products["price_category"] = (products["price"] / products["price"].max()) + (
#         products["category"] / products["category"].max()
#     )

#     model.fit(products[["price_category"]])


# def recommend_products_model(products_df, products, model_model, top_n=10):

#     user_data = products_df

#     user_data = user_data.merge(products, on="productId")

#     user_profile = user_data[["price_category"]].mean().values.reshape(1, -1)

#     distances, indices = model_model.kneighbors(user_profile, n_neighbors=top_n + 1)
#     similar_products = indices.flatten()[1:]

#     recommended_product_ids = products.iloc[similar_products]["productId"].values

#     purchased_products = products_df["productId"].unique()
#     final_recommendations = [
#         prod for prod in recommended_product_ids if prod not in purchased_products
#     ]

#     return final_recommendations[:top_n]


def get_recommend_product(product_id,  num_recommendations=5):
    try:
        rating_raw = pd.DataFrame(get_products())
        viewed_product_raw = pd.DataFrame(get_view_by_product(product_id))
        invoice_data = pd.DataFrame(get_invoices())
        # viewed_product_raw = viewed_product_raw.dropna()
        if viewed_product_raw.empty or invoice_data.empty or rating_raw.empty:
            app.logger.info("Empty data", viewed_product_raw.empty , invoice_data.empty , rating_raw.empty)
            return []
        
        viewed_product_raw = viewed_product_raw.rename(columns={'viewerId': 'userId', 'objectId': 'productId'})
        user_id_map = {id: idx + 1 for idx, id in enumerate(invoice_data['userId'].unique())}
        product_id_map = {id: idx + 1 for idx, id in enumerate(rating_raw['productId'].unique())}

        invoice_data.loc[:, 'userId_mapped'] = invoice_data['userId'].map(user_id_map)
        invoice_data.loc[:, 'productId_mapped'] = invoice_data['productId'].map(product_id_map)
        viewed_product_raw.loc[:, 'userId_mapped'] = viewed_product_raw['userId'].map(user_id_map)
        viewed_product_raw.loc[:, 'productId_mapped'] = viewed_product_raw['productId'].map(product_id_map)
        rating_raw.loc[:, 'productId_mapped'] = rating_raw['productId'].map(product_id_map)
        rating_raw.loc[:, 'userId_mapped'] = rating_raw['userId'].map(user_id_map)


        viewed_product = viewed_product_raw[['userId_mapped']]
        rating = rating_raw[['userId_mapped', 'productId_mapped','score']]
        #change the userId and productId to mapped values
       

        product_id_mapped = product_id_map[product_id]
        viewed_product = viewed_product.dropna(subset=['userId_mapped'])
        users_who_viewed = set(viewed_product['userId_mapped'])
        app.logger.info(rating);
        app.logger.info(users_who_viewed);

        relevant_invoices = rating[rating['userId_mapped'].isin(users_who_viewed)]
        app.logger.info(relevant_invoices);
        reader = Reader(rating_scale=(1, 5))  
        data = Dataset.load_from_df(relevant_invoices[['userId_mapped', 'productId_mapped', 'score']], reader)

        trainset, testset = train_test_split(data, test_size=0.1)
        model = load_or_train_model(trainset, MODEL_PATH_REC)
        model.fit(trainset)
        predictions = model.test(testset)
        sim_matrix = model.compute_similarities()
        app.logger.info(sim_matrix)


        y_true = [pred.r_ui for pred in predictions]
        y_pred = [pred.est for pred in predictions]
        print(f'y_true: {y_true[:10]}')
        print(f'y_pred: {y_pred[:10]}')
        inner_id = model.trainset.to_inner_iid(product_id_mapped)
        neighbors = model.get_neighbors(inner_id, k=num_recommendations)

        neighbors = [model.trainset.to_raw_iid(inner_id) for inner_id in neighbors]

        # neighbors = [list(product_id_map.keys())[list(product_id_map.values()).index(inner_id)] for inner_id in neighbors]

        similar_products = pd.DataFrame(neighbors, columns=['productId_mapped']).merge(rating_raw, left_on='productId_mapped', right_on='productId_mapped')

        similar_products = similar_products.drop_duplicates(subset=['productId'])
        similar_products_json = similar_products['productId'].tolist()
        response = {'listProduct': similar_products_json}
        return response
    except Exception as e:
        return {"message": "Error: " + str(e)}

def recommend_similar_products(product_id, num_recommendations=5):
    product_data = pd.DataFrame(get_products())
    product_id_map = {id: idx + 1 for idx, id in enumerate(product_data['productId'].unique())}
    
    product_data.loc[:, 'productId_mapped'] = product_data['productId'].map(product_id_map)
    
    product_data.dropna(subset=['productId_mapped', 'avgRating'], inplace=True)
    
    reader = Reader(rating_scale=(product_data['avgRating'].min(), product_data['avgRating'].max()))
    data = Dataset.load_from_df(product_data[['productId_mapped', 'productId_mapped', 'score']], reader)
    
    trainset, testset = train_test_split(data, test_size=0.2)
    
    model = load_or_train_model(trainset, MODEL_PATH_SIM)
    model.fit(trainset)
    
    if product_id not in product_id_map:
        raise ValueError(f"Product ID {product_id} is not part of the trainset")
    
    # Lấy inner_id của product_id
    inner_id = model.trainset.to_inner_iid(product_id_map[product_id])
    
    neighbors = model.get_neighbors(inner_id, k=num_recommendations)
    
    neighbors = [model.trainset.to_raw_iid(inner_id) for inner_id in neighbors]
    
    neighbors_mapped = [list(product_id_map.keys())[list(product_id_map.values()).index(n)] for n in neighbors]
    similar_products = pd.DataFrame(neighbors_mapped, columns=['productId']).merge(product_data, on='productId')
    similar_products_json = similar_products['productId'].tolist()
    response = {'listProduct': similar_products_json}
    return response

def load_or_train_model(trainset, model_path):
    if os.path.exists(model_path):
        model = joblib.load(model_path)
        app.logger.info("Model loaded")
    else:
        model = KNNBasic(sim_options=sim_options)
        model.fit(trainset)
        joblib.dump(model, model_path)
    return model


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
api.add_resource(SimilarProduct, "/similar-product/<product_id>")


if __name__ == "__main__":
    app.run(debug=False)
