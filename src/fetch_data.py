import requests
    import pandas as pd

    def fetch_data(api_endpoint):
        response = requests.get(api_endpoint)
        if response.status_code == 200:
            return pd.json(response.text)
        else:
            raise Exception(f"Не удалось получить данные с API: {response.status_code}")

    knowledge_data = fetch_data('Knowledge OS API endpoint')
