import logging
import requests

from tenacity import retry, wait_exponential, stop_after_attempt

logger = logging.getLogger(__name__)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=5))
def get_voice(text: str, voice: str):
    headers = {
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7,zh-TW;q=0.6",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Origin": "chrome-extension://klgfhbiooeogdfodpopgppeadghjjemk",
        "Pragma": "no-cache",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "none",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json",
    }
    language = None
    try:
        response = requests.post(
            "https://translate.volcengine.com/web/langdetect/v1/",
            headers=headers,
            json={"text": text},
        )
        language = response.json().get("language", None)
    finally:
        pass

    json_data = {
        "text": text,
        "speaker": voice,
    }

    if language is not None:
        json_data["language"] = language

    try:
        response = requests.post(
            "https://translate.volcengine.com/crx/tts/v1/",
            headers=headers,
            json=json_data,
        )
        response.raise_for_status()
    except Exception as e:
        logger.error(e)
        raise Exception(f"火山语音服务 {voice} 出错了。")
    resp = response.json()
    audio = resp.get("audio")
    if audio is None:
        logger.error(resp)
        raise Exception(f"火山语音服务 {voice} 生成失败，请切换音色后再试一次。")
    audio_data = audio.get("data", None)
    if audio_data is None:
        logger.error(resp)
        raise Exception(f"火山语音服务 {voice} 数据生成失败。")

    return audio_data