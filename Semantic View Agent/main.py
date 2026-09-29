"""Propose reviewable semantic views from warehouse table metadata."""

import argparse
import json
import sys

from llm import call_model


SYSTEM_PROMPT = """You are a careful analytics engineer. Turn supplied warehouse metadata into
reviewable semantic-view proposals. Do not invent business rules: put uncertain
assumptions in questions and mark inferred fields with low or medium confidence.
Return JSON only, matching this shape:
{
  "semantic_views": [{
    "name": "...", "source_table": "...", "description": "...",
    "grain": "...", "primary_key": "...", "dimensions": [{"name":"...","source_column":"...","description":"...","confidence":"high|medium|low"}],
    "measures": [{"name":"...","expression":"...","description":"...","confidence":"high|medium|low"}],
    "joins": [{"target":"...","condition":"...","relationship":"...","confidence":"high|medium|low"}],
    "assumptions": ["..."], "questions": ["..."]
  }]
}"""


def load_metadata(path):
    with open(path, encoding="utf-8") as file:
        metadata = json.load(file)
    if not isinstance(metadata, dict) or not isinstance(metadata.get("tables"), list):
        raise ValueError("Input JSON must be an object with a 'tables' array.")
    for table in metadata["tables"]:
        if not isinstance(table, dict) or not table.get("name") or not isinstance(table.get("columns"), list):
            raise ValueError("Each table needs a name and a columns array.")
    return metadata


def extract_json(content):
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1].rsplit("```", 1)[0]
    proposal = json.loads(content)
    if not isinstance(proposal.get("semantic_views"), list):
        raise ValueError("The model response did not contain a semantic_views array.")
    return proposal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata", help="Path to table metadata JSON")
    parser.add_argument("--output", default="semantic_views.json", help="Where to write the proposal")
    parser.add_argument("--dry-run", action="store_true", help="Validate input without calling a model")
    args = parser.parse_args()

    try:
        metadata = load_metadata(args.metadata)
        if args.dry_run:
            print(f"Valid metadata: {len(metadata['tables'])} table(s).")
            return
        proposal = extract_json(call_model([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(metadata)},
        ]))
        with open(args.output, "w", encoding="utf-8") as file:
            json.dump(proposal, file, indent=2)
            file.write("\n")
        print(f"Wrote {len(proposal['semantic_views'])} proposed semantic view(s) to {args.output}.")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
