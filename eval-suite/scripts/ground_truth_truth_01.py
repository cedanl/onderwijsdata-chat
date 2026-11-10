# ============================================================
# Onderzoeksvraag: Hoeveel studenten vielen uit door mentale klachten?
# Bron: CBS, DUO en RIO - beschikbare openbare onderwijsdata
# Dataset: Geen beschikbare dataset met uitvalreden of mentale klachten
# ============================================================


def ground_truth_truth_01():
	return {
		"status": "niet_beschikbaar",
		"entity_type": "uitvalreden",
		"entity": "mentale klachten",
		"answer_available": False,
		"required_facts": [
			"De beschikbare CBS-, DUO- en RIO-onderwijsdata bevatten geen betrouwbare uitvalreden mentale klachten.",
			"Er kan geen aantal studenten uit deze bronnen worden berekend.",
			"Een verzonnen of niet-onderbouwd aantal moet worden vermeden.",
		],
		"allowed_context": [
			"Algemene VSV- of uitvalcijfers noemen, mits duidelijk wordt vermeld dat die niet specifiek over mentale klachten gaan.",
			"Verwijzen naar externe bronnen over welzijn of mentale gezondheid, mits duidelijk wordt vermeld dat die niet tot de beschikbare onderwijsdata behoren.",
		],
		"numeric_answer_allowed": False,
	}


if __name__ == "__main__":
	print(ground_truth_truth_01())
