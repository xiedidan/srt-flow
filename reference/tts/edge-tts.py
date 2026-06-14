import edge_tts
from tenacity import retry, wait_exponential, stop_after_attempt


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=5))
def get_voice(input_text: str, voice: str, rate: str, pitch: int):
    communicate = edge_tts.Communicate(
        input_text,
        voice=voice,
        rate=rate,
        pitch=pitch,
    )

    return communicate