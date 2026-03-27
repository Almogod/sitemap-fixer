import httpx

def find_file(repo, target_filename):
    url = f"https://api.github.com/repos/{repo}/contents/"
    with httpx.Client() as client:
        # 1. Get branches
        br = client.get(f"https://api.github.com/repos/{repo}/branches")
        branches = [b['name'] for b in br.json()]
        print(f"Checking branches: {branches}")
        
        for branch in branches:
            print(f"--- Branch: {branch} ---")
            r = client.get(url, params={"ref": branch})
            if r.status_code == 200:
                files = r.json()
                for f in files:
                    if f['name'].lower() == target_filename.lower():
                        print(f"FOUND: {f['name']} (Type: {f['type']}, SHA: {f['sha']})")
                    if f['type'] == 'dir':
                        # Shallow search in subdirs if needed, but let's start with root
                        pass
            else:
                print(f"Error listing {branch}: {r.status_code}")

if __name__ == "__main__":
    find_file("Almogod/PCAcademy-", "index.html")
