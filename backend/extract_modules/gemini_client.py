import json
import time
from google import genai
from google.genai import types
from ..logger_config import get_logger

gemini_logger = get_logger("gemini_api", "gemini_api.log")

class GeminiClient:
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model_name = model_name
        self.client = None
        if api_key:
            try:
                self.client = genai.Client(api_key=api_key)
            except Exception as e:
                gemini_logger.error(f"Failed to init Gemini Client: {e}")

    def is_ready(self):
        return self.client is not None

    def segment_batch(self, transcripts_dict, custom_prompt=None):
        if not self.is_ready() or not transcripts_dict:
            return {}
        
        gemini_logger.info(f"Requesting Gemini ({self.model_name}) for {len(transcripts_dict)} files...")
        
        joined_transcripts = ""
        keys = list(transcripts_dict.keys())
        map_id_to_key = {f"VID_{i}": k for i, k in enumerate(keys)}
        
        for i, key in enumerate(keys):
            text = transcripts_dict[key]
            import os
            filename = os.path.basename(key)
            joined_transcripts += f"\n\n################################################################\n"
            joined_transcripts += f"### VIDEO_ID: VID_{i} (Source: {filename})\n"
            joined_transcripts += f"################################################################\n\n{text}\n"

        target_prompt = self._build_prompt(custom_prompt, joined_transcripts)
        
        input_char_count = len(target_prompt)
        gemini_logger.info(f"REQ: Model={self.model_name}, Files={len(transcripts_dict)}, InputSize={input_char_count} chars")

        max_retries = 5
        retry_delay = 10

        for attempt in range(max_retries):
            try:
                start_time = time.time()
                response = self.client.models.generate_content(
                    model=self.model_name,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    ),
                    contents=target_prompt
                )
                elapsed = time.time() - start_time
                
                finish_reason = "UNKNOWN"
                safety_info = "OK"
                
                if hasattr(response, 'candidates') and response.candidates:
                    cand = response.candidates[0]
                    finish_reason = str(cand.finish_reason)
                    if finish_reason != "STOP":
                         safety_info = str(cand.safety_ratings)
                
                gemini_logger.info(f"RES: Attempt={attempt+1}, Time={elapsed:.2f}s, Finish={finish_reason}, Safety={safety_info}")

                raw_result = None
                if response.text:
                    raw_result = json.loads(response.text)
                else:
                    gemini_logger.warning(f"RES WARN: Empty response text.")
                    return {}
                
                final_result = {}
                for vid, topics in raw_result.items():
                    if vid in map_id_to_key:
                        original_key = map_id_to_key[vid]
                        final_result[original_key] = topics
                
                return final_result

            except Exception as e:
                error_str = str(e)
                gemini_logger.error(f"ERR: Attempt={attempt+1}, Type={type(e).__name__}, Msg={e}")
                
                if "503" in error_str or "overloaded" in error_str.lower() or "429" in error_str:
                    gemini_logger.info(f"Retrying in {retry_delay}s due to overload/rate-limit...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    return {}
        
        gemini_logger.error("ERR: Max retries reached. Skipping batch.")
        return {}

    def _build_prompt(self, custom_prompt, joined_transcripts):
        if custom_prompt:
             if "{transcripts}" in custom_prompt:
                 return custom_prompt.replace("{transcripts}", joined_transcripts)
             else:
                 return custom_prompt + f"\n\nTRANSCRIPTS:\n{joined_transcripts}"
        else:
             return f"""
        You are a professional program editor. Analyze the following transcripts from multiple video files (separated by VIDEO_ID) and split each into distinct topics/segments.
        
        For each topic in each video, provide:
        1. start: The absolute starting timestamp (H:MM:SS.cs) EXACTLY as it appears in the text.
        2. end: The absolute ending timestamp (H:MM:SS.cs) EXACTLY as it appears in the text.
        3. title: A concise, catchy headline for the topic (Japanese).
        
        Rules:
        - **Grouping**: Identify distinct segments or topics (e.g., songs in a music show, corners in a variety show, news stories). **Group all related content** for the same segment into a single topic. 
        - **INCLUDE ALL CONTENT**: Commercials (CM), Opening, Ending, and transitions. 
        - **NO GAPS**: There should be NO gaps between topics. The end of one topic should be the start of the next.
        - **Labeling**: Label non-content segments clearly (e.g. "CM", "Opening").
        - **NO SUMMARY**: Do not generate a summary. Use only JSON format.
        - **TIMESTAMPS**: 
          - Must use the timestamps from the transcript lines.
          - **DO NOT** start from 0:00:00.00 unless the transcript actually starts there. 
        - **STRICT SEPARATION**: Each 'VIDEO_ID' block corresponds to a DIFFERENT and UNRELATED video file. 
          - **DO NOT** mix information between VIDEO_IDs. 
          - **DO NOT** let the topics of one video influence another.
          - Each VIDEO_ID must have its own independent list of topics in the output JSON.
        
        Output Format (JSON):
        {{
          "VID_0": [
              {{ "start": "0:05:23.00", "end": "0:06:45.00", "title": "Headline..." }},
              ...
          ]
        }}

        TRANSCRIPTS:
        {joined_transcripts}
        """
