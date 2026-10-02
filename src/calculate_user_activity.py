import psycopg2
from datetime import datetime

def calculate_user_activity(start_date, end_date):
    # Подключение к базе данных PostgreSQL с предполагаемыми учетными данными
    conn_string = "host='localhost' dbname='user_activity_db' user='yourusername' password='yourpassword' "
    conn = psycopg2.connect(conn_string)

    # Выборку SQL-запроса для подсчета количества действий GROUP BY user_id в указанный временной промежуток
    query = (
        "SELECT user_id, COUNT(*) as activity_count "
        "FROM user_activity "
        "WHERE action_timestamp BETWEe WHERE DATE(action_timestamp) BETWEen %s AND %s"
    ).format(start_date, end_date)

    # Выполнение SQL-запроса
    with psycopg2.connect(conn_string) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()

        # Преобразование результатов в словарь с user_id как ключами и подсчет активности как значений
        activity_counts = {row[0]: row[1] для row in rows}

    return activity_counts
