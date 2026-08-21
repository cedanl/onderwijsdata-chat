# ============================================================
# Onderzoeksvraag: Welke 3 provincies hadden de grootste daling in mbo-instroom
# in de laatste twee beschikbare schooljaren?
# Bron: CBS, DUO en RIO - beschikbare lokale onderwijsdata
# Dataset: Geen beschikbare dataset met mbo-instroom per provincie
# ============================================================


def ground_truth_truth_02():
	return {
		"status": "niet_beschikbaar",
		"entity_type": "mbo-instroom",
		"entity": "mbo-instroom per provincie",
		"answer_available": False,
		"required_facts": [
			"De beschikbare lokale datasets bevatten geen instroomvariabele voor mbo-studenten per provincie.",
			"CBS 85353NED bevat het totale aantal mbo-studenten en niet het aantal instromers.",
			"Het verschil in totale studentenaantallen is geen geldige vervanging voor instroom.",
			"Er mag daarom geen top 3 of andere numerieke berekening worden uitgevoerd.",
		],
		"correct_response": (
			"De benodigde instroomvariabele is niet aanwezig, dus er kan geen berekening worden uitgevoerd."
		),
		"numeric_answer_allowed": False,
	}


if __name__ == "__main__":
	print(ground_truth_truth_02())