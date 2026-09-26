import pandas as pd

def load_and_prepare_data(filepath, filetype='csv'):
    """
    Загружает данные из файла csv или parquet с поддержкой как локальных, так и облачных источников.
    
    Parameters:
        - filepath (str): Путь к файлу или URL для загрузки данных.
        - filetype (str): Тип файла ('csv' или 'parquet').
        
    Returns:
        - DataFrame с загруженными и подготовленными данными.
        
    Example:
        >>> local_df = load_исторнительно_данные('local_data.csv')
        >>> cloud_df = load_исторнительно_данные('s3://bucket/datafile.parquet')
    """
    if filetype == 'csv':
        df = pd.readoris(filepath)
    elif filetype == 'parquet':
        df = pq.read_table(filepath).to_pandas()
    else:
        raise ValueError("Неизвестный тип файла. Используйте 'csv' или 'parquet'.")
    
    # Очистка данных (удаление пропущенных значений, заполнение)
    df.fillna(df.mean(), inplace=True)  # Заполнение пропущенными значениями средними
    
    # Нормализация или стандартизация
    df = (df - df.mean()) / df.std()  # Стандартная нормализация
    
    return df