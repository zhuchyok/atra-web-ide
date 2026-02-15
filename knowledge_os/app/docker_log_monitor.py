class MockWebhookSender:
    def send(self, message):
        print(f"Mock sending: {message}")

class LogMonitor:
    def __init__(self):
        self.sender = MockWebhookSender()

    def monitor(self):
        self.sender.send("System check OK")
