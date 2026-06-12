import subprocess


def get_all_files():
    try:
        return subprocess.run(["ls"],capture_output=True,text=True).stdout.strip()
    except Exception as e:
        return f"Error: {e}"