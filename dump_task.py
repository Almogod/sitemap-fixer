import json

def dump_task(task_id, output_file):
    try:
        with open('tasks.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        task = data.get(task_id)
        if not task:
            print(f"Task {task_id} not found")
            return
            
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(task, f, indent=4)
        print(f"Dumped task {task_id} to {output_file}")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    dump_task("s79l8haujzh", "task_dump.json")
