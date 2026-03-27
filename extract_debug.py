import json

def extract_results(task_id):
    try:
        with open('tasks.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        task = data.get(task_id)
        if not task:
            print("Task not found")
            return
            
        res = task.get('results', {})
        print(json.dumps(res.get('deploy_results'), indent=4))
        
    except Exception as e:
        print(e)

if __name__ == "__main__":
    extract_results("hdm8xycsevt")
