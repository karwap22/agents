import subprocess
def calculator(expression: str):
    try:
        return str(eval(expression))
    except Exception as e:
        return f"Error: {e}"

def get_all_files():
    try:
        return subprocess.run(["ls"],capture_output=True,text=True).stdout.strip()
    except Exception as e:
        return f"Error: {e}"

def read_file(path: str):
    try:
        with open(path, "r") as f:
            return f.read()
    except Exception as e:
        return f"Error: {e}"


def search_web(query: str):
    # Mock implementation
    return f"Search results for '{query}'"