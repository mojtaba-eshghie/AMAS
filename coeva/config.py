import os

# Optional: load .env automatically
try:
    from dotenv import load_dotenv  # pip install python-dotenv
    load_dotenv()
except Exception:
    pass

PROVIDER = os.getenv('COEVA_LLM_PROVIDER', 'stub')  # 'stub' | 'openai'
BASE_URL = os.getenv('COEVA_OPENAI_BASE_URL', 'https://api.openai.com')
MODEL    = os.getenv('COEVA_OPENAI_MODEL', 'gpt-4o-mini')
API_KEY  = os.getenv('OPENAI_API_KEY', '')
TIMEOUT  = float(os.getenv('COEVA_LLM_TIMEOUT', '60'))

# Logging controls
LOG_JSONL = os.getenv('COEVA_LOG', '0') == '1'
LOG_DIR   = os.getenv('COEVA_LOG_DIR', 'logs')
LOG_LEVEL = os.getenv('COEVA_LOG_LEVEL', 'INFO').upper()   # DEBUG|INFO|WARN|ERROR
LOG_PROMPTS    = os.getenv('COEVA_LOG_PROMPTS', '0') == '1'
LOG_ARTIFACTS  = os.getenv('COEVA_LOG_ARTIFACTS', '0') == '1'
LOG_HTTP       = os.getenv('COEVA_LOG_HTTP', '0') == '1'
LOG_PREVIEW_CHARS = int(os.getenv('COEVA_LOG_PREVIEW', '240'))
SAVE_RAW    = os.getenv('COEVA_SAVE_RAW', '0') == '1'   # save raw LLM input/output files
RAW_DIR     = os.getenv('COEVA_RAW_DIR', 'logs/raw')    # where to put raw txt
ARTIFACTS_DIR = os.getenv('COEVA_ARTIFACTS_DIR', 'artifacts')  # save artifacts per step

# ── Reasoning-model safety knobs ──────────────────────────────────────────────
MAX_COMPLETION_TOKENS = int(os.getenv("COEVA_MAX_COMPLETION_TOKENS", "2048"))
MAX_COMPLETION_CEILING = int(os.getenv("COEVA_MAX_COMPLETION_CEILING", "8192"))
REASONING_EFFORT = os.getenv("COEVA_REASONING_EFFORT", "low")  # low|medium|high|omit


# Temperature (some models reject non-default); use "omit" to not send it
_raw_temp = os.getenv('COEVA_TEMPERATURE', '0.7')
if _raw_temp.strip().lower() in ('', 'none', 'omit'):
    TEMPERATURE = None
else:
    try:
        TEMPERATURE = float(_raw_temp)
    except Exception:
        TEMPERATURE = 0.7
