def parse_prompt(prompt):
    try:
        data = json.loads(prompt)
        return data
    except json.JSONDecodeError:
        return None