import json
import os

def extract_deploy_info(task_id):
    try:
        with open('tasks.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        task = data.get(task_id)
        if not task:
            print(f"Task {task_id} not found")
            return
            
        # The deploy_config might be in the task metadata if I saved it
        # Actually, in app.py:
        # background_tasks.add_task(apply_approved_plugin_fixes, task_id, approved_action_ids, ...)
        # The deploy_config isn't saved in the report results usually.
        # WAIT, let me check where deploy_config comes from.
        print(f"Task Status: {task.get('status')}")
        print(f"Status Msg: {task.get('status_msg')}")
        
        results = task.get('results', {})
        print(f"Repo: {results.get('deploy_results', [{}])[0].get('repo')}")
        print(f"Branch: {results.get('deploy_results', [{}])[0].get('branch')}")
        print(f"Path: {results.get('deploy_results', [{}])[0].get('file_path')}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    extract_deploy_info("s79l8haujzh")
