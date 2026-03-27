import httpx

def check_github_repo(repo):
    # Public check
    url = f"https://api.github.com/repos/{repo}"
    print(f"Checking Repo: {url}")
    with httpx.Client() as client:
        r = client.get(url)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"Full Name: {data.get('full_name')}")
            print(f"Default Branch: {data.get('default_branch')}")
            
            # Check branches
            b_url = f"{url}/branches"
            br = client.get(b_url)
            if br.status_code == 200:
                branches = [b['name'] for b in br.json()]
                print(f"Branches: {branches}")
        else:
            print(f"Error: {r.text}")

if __name__ == "__main__":
    check_github_repo("almogod/PCAcademy-")
    print("\n--- Try Capitalized ---")
    check_github_repo("Almogod/PCAcademy-")
