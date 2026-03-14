import base64
import requests


def get_file(repo, path, token):

    url = f"https://api.github.com/repos/{repo}/contents/{path}"

    headers = {"Authorization": f"token {token}"}

    r = requests.get(url, headers=headers)

    if r.status_code != 200:
        return None

    data = r.json()

    content = base64.b64decode(data["content"]).decode()

    return {
        "content": content,
        "sha": data["sha"]
    }


def update_file(repo, path, content, sha, token, message):

    url = f"https://api.github.com/repos/{repo}/contents/{path}"

    headers = {"Authorization": f"token {token}"}

    payload = {
        "message": message,
        "content": base64.b64encode(content.encode()).decode(),
        "sha": sha
    }

    r = requests.put(url, json=payload, headers=headers)

    return r.json()
