import re
import json

def extract_experts(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Optimized pattern to find all experts in .cursorrules
    # It matches "### **N. Name - Role**"
    expert_pattern = r'### \*\*(\d+)\. (.*?) - (.*?)\*\*'
    
    experts = []
    # Find all start positions of expert headers
    starts = [m.start() for m in re.finditer(expert_pattern, content)]
    
    for i in range(len(starts)):
        start = starts[i]
        end = starts[i+1] if i+1 < len(starts) else len(content)
        chunk = content[start:end]
        
        match = re.search(expert_pattern, chunk)
        if match:
            original_id = match.group(1)
            name = match.group(2).strip()
            role = match.group(3).strip()
            # Everything after the header in this chunk
            tasks = chunk[match.end():].strip()
            
            # Clean up trailing section markers if present
            tasks = re.split(r'\n##\s|\n---\s', tasks)[0].strip()
            
            system_prompt = f"You are {name}, {role}.\n{tasks}"
            
            experts.append({
                "name": name,
                "role": role,
                "system_prompt": system_prompt,
                "metadata": {"original_id": original_id}
            })

    return experts

def generate_sql(experts):
    sql_lines = ["-- Seed All Experts Data"]
    for exp in experts:
        safe_prompt = exp['system_prompt'].replace("'", "''")
        line = f"INSERT INTO experts (name, role, system_prompt, metadata) VALUES ('{exp['name']}', '{exp['role']}', '{safe_prompt}', '{json.dumps(exp['metadata'])}') ON CONFLICT (name) DO UPDATE SET system_prompt = EXCLUDED.system_prompt;"
        sql_lines.append(line)
    return "\n".join(sql_lines)

if __name__ == "__main__":
    try:
        experts = extract_experts(".cursorrules")
        sql_content = generate_sql(experts)
        
        with open("knowledge_os/db/seed_experts.sql", "w", encoding="utf-8") as f:
            f.write(sql_content)
            
        print(f"Successfully extracted {len(experts)} experts.")
    except Exception as e:
        print(f"Error: {e}")
