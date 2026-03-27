import os

def find_task_id_by_line(line_num):
    # This is a bit tricky with JSON, but I can read backwards from the line
    # to find the key of the top-level object.
    with open('tasks.json', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    # Search upwards from line_num for the start of a top-level key like '"id": {'
    # or just the start of the object if formatted as '"id": {' at the root.
    target_idx = line_num - 1 # 0-indexed
    
    # Simple heuristic: find '"[task_id]": {' at the root level (indent 4 presumably)
    for i in range(target_idx, -1, -1):
        line = lines[i]
        if line.startswith('    "'):
            # This might be the task ID. e.g. '    "abc123def": {'
            if '{' in line:
                task_id = line.split('"')[1]
                print(f"Potential Task ID: {task_id}")
                return task_id
    return None

if __name__ == "__main__":
    task_id = find_task_id_by_line(252365)
    if task_id:
        # Now dump it
        import json
        with open('tasks.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        task = data.get(task_id)
        if task:
            with open('failed_task_debug.json', 'w', encoding='utf-8') as f:
                json.dump(task, f, indent=4)
            print(f"Dumped to failed_task_debug.json")
