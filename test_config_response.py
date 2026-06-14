"""
Test script to verify ASR config response includes gemini_base_url
"""
from backend.core.config import ASRConfig
import json

# Create default ASR config
config = ASRConfig()

# Dump with exclude_none=False (should include gemini_base_url)
data_with_none = config.model_dump(exclude_none=False)
print("With exclude_none=False:")
print(json.dumps(data_with_none, indent=2))
print(f"\ngemini_base_url in data: {'gemini_base_url' in data_with_none}")
print(f"gemini_base_url value: {data_with_none.get('gemini_base_url')}")

# Dump with exclude_none=True (should exclude gemini_base_url)
data_without_none = config.model_dump(exclude_none=True)
print("\n\nWith exclude_none=True:")
print(json.dumps(data_without_none, indent=2))
print(f"\ngemini_base_url in data: {'gemini_base_url' in data_without_none}")
