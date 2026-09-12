from openai import OpenAI
from pydantic import BaseModel, Field
from typing import List
from configs.settings import settings

class BinaryHypothesis(BaseModel):
    strategy_id: str
    pair: str
    direction: str # CALL/PUT
    expiry: int # 5 or 10
    trigger: str
    confidence_floor: float = 0.62
    regime_affinity: str
    ev_estimate: float

class BinaryResearcher:
    def __init__(self):
        self.client = OpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url=settings.GROQ_BASE_URL
        )
        self.model = settings.RESEARCHER_MODEL

    async def generate_binary_idea(self, tick_data: str) -> BinaryHypothesis:
        pass

binary_researcher = BinaryResearcher()
