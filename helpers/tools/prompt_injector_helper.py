import csv

def load_csv_texts(path):
	texts = []
	try:
		with open(path, newline="", encoding="utf-8") as fh:
			reader = csv.reader(fh)
			for row in reader:
				texts.append(",".join([c.strip() for c in row]))
	except Exception:
		return []
	return texts

def load_prompts_from_db(db):
	try:
		prompts = db.get_all_generated_prompts()
		return [(row[0], row[2]) for row in prompts if row[2]]
	except Exception:
		return []


def load_text_texts(path):
	"""Load prompts from a plain text file.

	Parsing rules:
	- Each non-empty line is treated as a single prompt.
	- Lines are stripped of surrounding whitespace; empty lines are ignored.
	- Commas inside a line are preserved (so prompts may contain commas).
	"""
	texts = []
	try:
		with open(path, "r", encoding="utf-8") as fh:
			lines = fh.read().splitlines()
			for line in lines:
				p = line.strip()
				if p:
					texts.append(p)
	except Exception:
		return []
	return texts
