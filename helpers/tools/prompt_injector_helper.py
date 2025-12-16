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
		# return list of (id, prompt_text)
		return [(row[0], row[2]) for row in prompts if row[2]]
	except Exception:
		return []
