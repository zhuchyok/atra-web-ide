# pattern_discovery.py

import pandas as pd
from sklearn.decomposition import PCA

def discover_patterns(data):
    # Преобразование данных
    df = pd.DataFrame(data)
    # Применение PCA для выявления основных паттернов
    pca = PCA(n_components=2)
    principalComponents = pca.fit_transform(df)
    return principalComponents

# Example usage
# patterns = discover_patterns(data)