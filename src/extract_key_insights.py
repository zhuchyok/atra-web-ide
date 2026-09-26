import pandas as pd
import numpy as np
from sklearn.feature_extraction import text
from sklearn.decomposition import PCA

def extract_key_insights(dataframe):
    # Нормализация данных
    dataframe = dataframe.fillna(method='ffill')
    
    # Выделение ключевых метрик
    key_metrics = dataframe[[ 'Revenue', 'Profit Margin', 'Market Share' ]]
    
    # Выявление паттернов с использованием PCA
    text_metrics = dataframe[['Product', 'Market', 'Region']].apply(lambda x: ' '.join(x), axis=1)
    vectorizer = text.CountVectorizer()
    matrix = vectorizer.fit_transform(text_metrics)
    pca = PCA(n_components=2)
    matrix_2d = pca.fit_transform(matrix)
    
    # Добавление 2D-паттернов в DataFrame
    key_metrics['PC1'], key_metrics['PC2'] = matrix_2d.tolist()
    
    return key_metrics[['PC1', 'PC2', 'Revenue', 'Profit Margin', 'Market Share']].to_json(orient='records')

# Пример использования:
# df_metrics = pd.read_csv('data_file.csv')
# insights = extract_key_insights(df_metrics)