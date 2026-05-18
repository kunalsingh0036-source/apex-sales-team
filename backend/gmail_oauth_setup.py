"""
Gmail OAuth2 Setup Script
Run this to get a refresh token for the Gmail API.
It will open a browser window for you to authorize access.
"""

import os
import sys

# Load .env file manually
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
env_vars = {}
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            env_vars[key.strip()] = val.strip()

CLIENT_ID = env_vars.get("GMAIL_CLIENT_ID", "").strip()
CLIENT_SECRET = env_vars.get("GMAIL_CLIENT_SECRET", "").strip()

if not CLIENT_ID or not CLIENT_SECRET:
    print("ERROR: GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET must be set in .env")
    sys.exit(1)

from google_auth_oauthlib.flow import InstalledAppFlow

# Gmail API scopes needed
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
]

# Build client config from env vars
client_config = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}

print("=" * 60)
print("  Gmail OAuth Setup for Apex Sales Agent")
print("=" * 60)
print()
print("A browser window will open. Sign in with:")
print(f"  {env_vars.get('GMAIL_SENDER_EMAIL', 'your Gmail account')}")
print()
print("Grant access to send and read emails.")
print()

flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
# Let the library pick a random free port (avoids redirect_uri_mismatch)
credentials = flow.run_local_server(port=8080, prompt="consent", access_type="offline")

refresh_token = credentials.refresh_token

if refresh_token:
    print()
    print("=" * 60)
    print("  SUCCESS! Here is your refresh token:")
    print("=" * 60)
    print()
    print(f"  {refresh_token}")
    print()
    print("Add this to your .env file:")
    print(f'  GMAIL_REFRESH_TOKEN={refresh_token}')
    print()

    # Offer to update .env automatically
    answer = input("Update .env automatically? (y/n): ").strip().lower()
    if answer == "y":
        with open(env_path, "r") as f:
            content = f.read()
        if "GMAIL_REFRESH_TOKEN=" in content:
            lines = content.split("\n")
            new_lines = []
            for line in lines:
                if line.startswith("GMAIL_REFRESH_TOKEN="):
                    new_lines.append(f"GMAIL_REFRESH_TOKEN={refresh_token}")
                else:
                    new_lines.append(line)
            content = "\n".join(new_lines)
        else:
            content = content.rstrip() + f"\nGMAIL_REFRESH_TOKEN={refresh_token}\n"
        with open(env_path, "w") as f:
            f.write(content)
        print(".env updated successfully!")
    print()
    print("Restart the backend for changes to take effect.")
else:
    print()
    print("ERROR: No refresh token received.")
    print("Make sure you selected 'offline' access and granted all permissions.")
