try:
    from ..extract_modules.subtitle import extract_subtitles_srt, get_transcript_text
    from ..extract_modules.gemini_client import GeminiClient
except (ImportError, ValueError):
    try:
        from extract_modules.subtitle import extract_subtitles_srt, get_transcript_text
        from extract_modules.gemini_client import GeminiClient
    except ImportError:
        from backend.extract_modules.subtitle import extract_subtitles_srt, get_transcript_text
        from backend.extract_modules.gemini_client import GeminiClient

MODEL_NAME = "gemini-2.5-flash"

def segment_batch_with_gemini(transcripts_dict, custom_prompt=None, model_name=None, api_key=None):
    client = GeminiClient(api_key=api_key, model_name=model_name or MODEL_NAME)
    return client.segment_batch(transcripts_dict, custom_prompt)

def get_gemini_client(api_key):
    client = GeminiClient(api_key=api_key)
    return client.client if client.is_ready() else None

__all__ = ["extract_subtitles_srt", "get_transcript_text", "segment_batch_with_gemini", "get_gemini_client", "MODEL_NAME"]
