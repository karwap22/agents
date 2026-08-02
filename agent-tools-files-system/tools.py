from pathlib import Path
import subprocess


def get_all_files():
    try:
        return subprocess.run(["ls"],capture_output=True,text=True).stdout.strip()
    except Exception as e:
        return f"Error: {e}"
    



def read_file(file_path: str) -> dict:
    try:
        path = Path(file_path)

        if not path.exists():
            return {
                "success": False,
                "error": f"File '{file_path}' does not exist."
            }

        if not path.is_file():
            return {
                "success": False,
                "error": f"'{file_path}' is not a file."
            }

        content = path.read_text(encoding="utf-8")

        return {
            "success": True,
            "content": content
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


