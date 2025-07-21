"""
Configuration settings for the Developer Dashboard
"""
import os

# Demo Mode Configuration
# Set to True to use dummy data instead of real API calls
# Set to False to use real GitHub API calls
DEMO_MODE = True

# GitHub API Configuration
GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_API_VERSION = "v3"

# Cache Configuration
CACHE_TTL_SECONDS = 43200  # 12 hours
CACHE_TTL_ERROR_SECONDS = 300  # 5 minutes for errors

# Rate Limiting Configuration
MAX_CONCURRENT_REQUESTS = 8
REQUEST_DELAY = 0.1  # seconds
INITIAL_PR_FETCH_COUNT = 20

# Demo Mode Messages
DEMO_MODE_BANNER = """
🎭 DEMO MODE ACTIVE
Using realistic dummy data for demonstration purposes.
To use real GitHub data, set DEMO_MODE = False in config.py
"""

# Environment-based configuration override
if os.getenv('DEMO_MODE'):
    DEMO_MODE = os.getenv('DEMO_MODE').lower() == 'true'

# Flask Configuration
FLASK_DEBUG = True
FLASK_PORT = 5000
FLASK_HOST = '127.0.0.1' 