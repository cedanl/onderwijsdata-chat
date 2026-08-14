# ============================================================
# Onderzoeksvraag: Hoeveel is het aantal HBO-studenten gedaald sinds 2018, op landelijk niveau?
# Bron: CBS OData API - Hoger onderwijs; ingeschrevenen, onderwijssoort, opleidingsfase en -vorm
# Dataset: 85423NED
# ============================================================

from pathlib import Path

import pandas as pd


def ground_truth_conflict_01(
	data_path=Path("data/raw/85423NED_UntypedDataSet_20260810161207.csv")
):
	df = pd.read_csv(data_path, sep=";", encoding="utf-8-sig")
	df["TotaalIngeschrevenen_1"] = pd.to_numeric(
		df["TotaalIngeschrevenen_1"].astype(str).str.strip(),
		errors="raise",
	)

	df = df.loc[
		(df["Geslacht"] == "T001038")
		& (df["Onderwijssoort"] == "A025294")
		& (df["Opleidingsfase"] == "A045745")
		& (df["Opleidingsvorm"] == "T001228")
	].sort_values("Perioden")

	start_period = "2018SJ00"
	eind_period = df["Perioden"].iloc[-1]
	periode_selectie = df.loc[
		(df["Perioden"] >= start_period) & (df["Perioden"] <= eind_period)
	].copy()
	start = periode_selectie.loc[
		periode_selectie["Perioden"] == start_period, "TotaalIngeschrevenen_1"
	].iloc[0]
	eind = periode_selectie.loc[
		periode_selectie["Perioden"] == eind_period, "TotaalIngeschrevenen_1"
	].iloc[0]
	verandering = int(eind - start)

	jaarlijkse_verandering = periode_selectie["TotaalIngeschrevenen_1"].diff().dropna()

	return {
		"start_schooljaar": "2018/'19",
		"eind_schooljaar": f"{eind_period[:4]}/'{str(int(eind_period[:4]) + 1)[-2:]}",
		"start_aantal": int(start),
		"eind_aantal": int(eind),
		"verandering": verandering,
		"daling": int(-verandering) if verandering < 0 else 0,
		"verandering_pct": round(float(verandering / start * 100), 2),
		"netto_daling": verandering < 0,
		"continue_daling": bool((jaarlijkse_verandering < 0).all()),
		"premisse_toelichting": (
			"Er is een netto daling sinds 2018/'19, maar het aantal daalde niet elk jaar."
		),
	}


if __name__ == "__main__":
	print(ground_truth_conflict_01())