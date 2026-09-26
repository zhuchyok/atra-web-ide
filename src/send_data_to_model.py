import json

def send_data_to_model(data, model_api):
    url = model_api['endpoint']
    headers = {'content-type': 'application/json'}
    
    data_json = data.to_json()
    response = requests.post(url, headers=headers, data=json.dumps(data_json))
    
    if response.status_code == 200:
        logger.info("Data successfully sent to the model.")
    else:
        logger.error(f"Failed to send data to the model. Status code: {response.status_code}")

# Пример использования:
model_api = {
    "endpoint": "https://api.knowledge-os.local/v1/predict"
}

# Предполагаем, что мы уже загрузили данные в DataFrame под названием 'processed_data'
send_data_to_model(processed_data, model_api)