"""
Стресс-тестирование ATRA Web IDE (День 6–7, Фаза 3).
Locust: чат (stream), план, смешанная нагрузка.
"""
import random
import time
from locust import HttpUser, task, between


class ChatUser(HttpUser):
    """Пользователь, имитирующий запросы к чату и планам."""

    wait_time = between(1, 3)

    def on_start(self):
        self.user_id = f"user_{random.randint(1000, 9999)}"

    @task(3)
    def ask_simple_query(self):
        """Простые запросы."""
        queries = ["привет", "как дела", "спасибо", "пока"]
        self._send_chat_stream(random.choice(queries), "ask")

    @task(2)
    def ask_factual_query(self):
        """Фактуальные запросы."""
        queries = [
            "сколько стоит подписка",
            "как создать аккаунт",
            "время работы поддержки",
            "документация API",
            "как сбросить пароль",
        ]
        self._send_chat_stream(random.choice(queries), "ask")

    @task(1)
    def ask_complex_query(self):
        """Сложные запросы."""
        queries = [
            "проанализируй мои логи и найди ошибки",
            "сравни производительность двух алгоритмов",
            "разработай план по миграции базы данных",
        ]
        self._send_chat_stream(random.choice(queries), "ask")

    @task(1)
    def create_plan(self):
        """Создание планов."""
        plans = [
            "план по настройке мониторинга",
            "стратегия развертывания приложения",
            "план миграции на облако",
            "оптимизация производительности базы данных",
        ]
        with self.client.post(
            "/api/chat/plan",
            json={"goal": random.choice(plans)},
            catch_response=True,
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status {response.status_code}")

    def _send_chat_stream(self, query: str, mode: str):
        """POST /api/chat/stream (SSE)."""
        with self.client.post(
            "/api/chat/stream",
            json={
                "content": query,
                "mode": mode,
                "user_id": self.user_id,
            },
            stream=True,
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"Status {response.status_code}")
                return
            try:
                for _ in response.iter_lines():
                    pass
                response.success()
            except Exception as e:
                response.failure(str(e))


class StressTestUser(HttpUser):
    """Высокая нагрузка (короткие интервалы)."""

    wait_time = between(0.1, 0.3)

    @task(10)
    def heavy_load(self):
        self.client.post(
            "/api/chat/stream",
            json={
                "content": "стресс тест",
                "mode": "ask",
                "user_id": f"stress_{random.randint(10000, 99999)}",
            },
        )
