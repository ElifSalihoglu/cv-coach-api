import asyncio

from app.models.schemas import CVOptimizeRequest, GeneratedCVContent
from app.prompts.cv_templates import BASE_CV_SYSTEM_PROMPT
from app.services.cv_coach import OpenAICVCoach


class FakeLLMClient:
    def __init__(self, result):
        self.result = result
        self.calls = []

    async def generate(self, system_prompt, user_content):
        self.calls.append({"system_prompt": system_prompt, "user_content": user_content})
        return self.result


def test_optimize_sends_candidate_input_and_returns_generated_content():
    generated = GeneratedCVContent(
        improved_bullets=["Automated weekly reporting with Python."],
        summary="Python developer focused on data automation.",
        linkedin_headline="AI Engineer | Python | Data Automation",
    )
    llm = FakeLLMClient(generated)
    coach = OpenAICVCoach(llm_client=llm)
    request = CVOptimizeRequest(
        job_title="AI Engineer",
        job_description="Build and maintain Python APIs.",
        current_bullets=["Automated weekly reports with Python."],
    )

    response = asyncio.run(coach.optimize(request))

    assert llm.calls[0]["system_prompt"] == BASE_CV_SYSTEM_PROMPT
    assert llm.calls[0]["user_content"] == {
        "job_title": "AI Engineer",
        "job_description": "Build and maintain Python APIs.",
        "current_bullets": ["Automated weekly reports with Python."],
    }
    assert response.improved_bullets == generated.improved_bullets
    assert response.summary == generated.summary
    assert response.linkedin_headline == generated.linkedin_headline
    assert response.retrieved_jobs == []
