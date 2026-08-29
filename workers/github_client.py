import jwt
from datetime import datetime,timezone 
import httpx
from api.config import settings


def create_jwt()->str:
    if settings.github_app_private_key:
        private_key = settings.github_app_private_key.replace("\\n", "\n")
    elif settings.github_app_private_key_path:
        with open(settings.github_app_private_key_path, "r") as f:
            private_key = f.read()
    else:
        raise ValueError("Neither GITHUB_APP_PRIVATE_KEY nor GITHUB_APP_PRIVATE_KEY_PATH is configured")

    now = int(datetime.now(timezone.utc).timestamp())

    payload={
        "iat":now-60,
        "exp":now + 540,
        "iss":str(settings.github_app_id),
    }
    return jwt.encode(payload,private_key,algorithm="RS256")
    
def get_installation_token()->str:
    token=create_jwt()

    url=f"https://api.github.com/app/installations/{settings.github_app_installation_id}/access_tokens"
    headers={
        "Authorization":f"Bearer {token}",
        "Accept":"application/vnd.github+json",
    } 
    response=httpx.post(url,headers=headers)
    response.raise_for_status()

    return response.json()["token"]