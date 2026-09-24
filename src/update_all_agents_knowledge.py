import logging
import logging.handlers

# Настройка логгера
logging.basicConfig(level=logging.ERROR,
                      format='%(asctime)s - %(levelname)s - %(message)s')

# Имитация вызова функции в контейнере
def update_all_agents_knowledge():
    try:
        # Логика, которая могла бы вызывать ошибку
        pass  # Здесь должен быть код, который вызывает ошибку
        logging.info("Agents knowledge updated successfully.")
    except Exception as e:
        logging.error("Exception in update_all_agents_knowledge: %s", str(e))

# Тестирование вызова функции
update_allзуин