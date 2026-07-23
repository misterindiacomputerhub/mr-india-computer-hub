"""
upload_agent.py
Uploads a rendered video to YouTube via the YouTube Data API v3.
This stage needs almost no changes from a general-purpose pipeline — reuse
as-is.

First-time setup:
1. Create a project in Google Cloud Console, enable "YouTube Data API v3".
2. Create an OAuth Client ID (Desktop app), download as client_secret.json.
3. First run will open a browser to authorize; a token.json is cached after.
"""
import os
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.http
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]
def _resolve_secret_to_file(env_var_name, default_filename):
    """
    Cloud Run secret env vars sometimes contain raw JSON content instead of
    a file path. If the value looks like JSON, write it to a temp file and
    return that path. Otherwise treat it as an actual file path already.
    """
    raw = os.getenv(env_var_name, default_filename)
    stripped = raw.strip()
    if stripped.startswith("{"):
        temp_path = f"/tmp/{default_filename}"
        with open(temp_path, "w") as f:
            f.write(raw)
        return temp_path
    return raw


CLIENT_SECRETS_FILE = _resolve_secret_to_file("YT_CLIENT_SECRETS_FILE", "client_secret.json")
TOKEN_FILE = _resolve_secret_to_file("YT_TOKEN_FILE", "token.json")


def get_authenticated_service():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRETS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())
    return googleapiclient.discovery.build("youtube", "v3", credentials=creds)


def upload_video(file_path: str, title: str, description: str, tags: list[str], category_id="28") -> str:
    """category_id 28 = Science & Technology. Change per content type if desired."""
    youtube = get_authenticated_service()
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }
    media = googleapiclient.http.MediaFileUpload(file_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%")

    return response["id"]


def fetch_video_stats(youtube_video_id: str) -> dict:
    youtube = get_authenticated_service()
    resp = youtube.videos().list(part="statistics", id=youtube_video_id).execute()
    items = resp.get("items", [])
    if not items:
        return {"views": 0, "likes": 0, "comments": 0}
    stats = items[0]["statistics"]
    return {
        "views": int(stats.get("viewCount", 0)),
        "likes": int(stats.get("likeCount", 0)),
        "comments": int(stats.get("commentCount", 0)),
    }
