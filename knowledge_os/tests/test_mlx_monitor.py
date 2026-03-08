import asyncio
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from knowledge_os.app.mlx_monitor import MLXMonitor


class TestMLXMonitor(unittest.TestCase):
    def setUp(self):
        self.monitor = MLXMonitor(window_size=5)

    def test_initial_health_score(self):
        self.assertEqual(self.monitor.get_health_score(), 1.0)

    def test_metrics_tracking(self):
        self.monitor.report_metrics(ttft=0.1, tbt=0.05, tps=20.0)
        self.monitor.record_success()
        self.assertEqual(self.monitor.get_health_score(), 1.0)

    def test_health_score_degradation_tbt(self):
        for _ in range(5):
            self.monitor.report_metrics(ttft=0.1, tbt=0.3, tps=5.0)
            self.monitor.record_success()

        score = self.monitor.get_health_score()
        self.assertLess(score, 1.0)

    def test_health_score_degradation_queue(self):
        self.monitor.update_queue_depth(10)
        score = self.monitor.get_health_score()
        self.assertLess(score, 1.0)

    def test_health_score_unreachable(self):
        self.monitor.record_failure()
        self.monitor.record_failure()
        self.monitor.record_failure()
        self.monitor.set_reachable(False)
        self.assertEqual(self.monitor.get_health_score(), 0.0)


class TestRouterIntegration(unittest.IsolatedAsyncioTestCase):
    @patch("httpx.AsyncClient")
    async def test_router_integration_warmup(self, mock_client_class):
        # Setup mock client
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock health check response
        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {
            "message": {"content": "Different response to avoid echo detection"}
        }
        mock_client.get.return_value = mock_response_200
        mock_client.post.return_value = mock_response_200

        # Patch get_mlx_monitor in local_router
        with patch("knowledge_os.app.local_router.get_mlx_monitor") as mock_get_monitor:
            mock_monitor = MagicMock()
            mock_get_monitor.return_value = mock_monitor
            mock_monitor.get_health_score.return_value = 0.4

            from knowledge_os.app.local_router import LocalAIRouter

            router = LocalAIRouter()

            # Test if run_local_llm triggers predictive warmup
            with patch.object(
                router, "_trigger_predictive_warmup", new_callable=AsyncMock
            ) as mock_warmup:
                await router.run_local_llm(prompt="test prompt", category="fast")
                mock_warmup.assert_called()


if __name__ == "__main__":
    unittest.main()
