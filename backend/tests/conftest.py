"""Pytest configuration and global fixtures."""

import os

# Ensure tests have a fallback mock key so config import does not crash during test runs
os.environ.setdefault("GROQ_API_KEY", "mock-test-groq-key-for-pytest")
os.environ.setdefault("GEMINI_API_KEY", "mock-test-key-for-pytest")
