#!/usr/bin/env python3
"""Simple test to verify Gemini API connectivity (like build_ai_summary.py)."""

import os
import time
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

# Load .env
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

print("=" * 60)
print("Gemini API Test (like build_ai_summary.py)")
print("=" * 60)
print(f"Model: {GEMINI_MODEL}")
print(f"API Key: {'SET' if GEMINI_API_KEY else 'NOT SET'}")
print()

if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY not set in .env")
    exit(1)

# Initialize client
client = genai.Client(api_key=GEMINI_API_KEY)


def generate_with_retry(call_fn, max_retries=8):
    """Retry with exponential backoff and jitter (from build_ai_summary.py)."""
    import random

    delay = 8.0
    for attempt in range(max_retries):
        try:
            return call_fn()
        except genai_errors.ClientError as e:
            msg = str(e)
            print(f"   [Attempt {attempt + 1}/{max_retries}] Error: {msg[:100]}")
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                jittered_delay = delay + random.random()
                print(f"   [AI] Rate limited. Retrying in {jittered_delay:.1f}s...")
                time.sleep(jittered_delay)
                delay = min(delay * 2, 20)
                continue
            raise


# Test simple query
print("Sending prompt: 'What was World War 2? Answer in 2-3 sentences.'")
print()

try:
    response = generate_with_retry(
        lambda: client.models.generate_content(
            model=GEMINI_MODEL,
            contents="What was World War 2? Answer in 2-3 sentences.",
            config=types.GenerateContentConfig(temperature=0.7),
        )
    )

    if response and response.text:
        print("✓ SUCCESS - Gemini responded:")
        print()
        print(response.text)
        print()
        print("=" * 60)
        print("API is working! Ready for background_backfill.py")
        print("=" * 60)
    else:
        print("✗ ERROR: No response from Gemini")

except Exception as e:
    print(f"✗ FAILED: {e}")
    import traceback

    traceback.print_exc()
