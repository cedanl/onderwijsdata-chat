import litellm
from config import MODEL
from .models import litellm_kwargs


async def generate_title(question: str, answer: str, model: str | None = None) -> str:
    chosen_model = model or MODEL
    response = await litellm.acompletion(
        model=chosen_model,
        max_tokens=20,
        num_retries=3,
        messages=[{
            "role": "user",
            "content": (
                "Geef een titel van maximaal 6 woorden voor dit gesprek. "
                "Alleen de titel zelf, geen uitleg of aanhalingstekens.\n\n"
                f"Vraag: {question[:400]}\nAntwoord: {answer[:400]}"
            ),
        }],
        **litellm_kwargs(chosen_model),
    )
    return response.choices[0].message.content.strip().strip('"\'')
