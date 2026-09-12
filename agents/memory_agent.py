from openai import OpenAI
from configs.settings import settings

class MemoryAgent:
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.GEMINI_KEY_1,
            base_url=settings.GEMINI_BASE_URL
        )
        self.model = settings.MEMORY_MODEL

    def log_event(self, event_type: str, data: dict):
        """Encodes experiences into Success DNA or Mistake Memory."""
        pass

memory_agent = MemoryAgent()
