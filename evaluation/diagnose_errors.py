import pandas as pd

from src.analytics import compute_baseline_and_anomalies


EXCEL_PATH = "Time_2025_Q1_Q3_fake_Python.xlsx"
BASELINE_DAYS = 30
ALERT_MINUTES = 30


def main():
    registros = pd.read_excel(EXCEL_PATH, sheet_name="Registros")
    truth = pd.read_excel(EXCEL_PATH, sheet_name="GroundTruth")

    registros["Data"] = pd.to_datetime(registros["Data"]).dt.date
    truth["Data"] = pd.to_datetime(truth["Data"]).dt.date

    truth_map = {
        (str(r.EmployeeID), r.Data): bool(r.InjectedDeviation)
        for r in truth.itertuples()
    }

    results = []

    for employee_id, group in registros.groupby("EmployeeID"):
        group = group.sort_values("Data")

        records = group[
            ["EmployeeID", "Data", "Entrada", "Saida"]
        ].to_dict("records")

        baseline, anomalies = compute_baseline_and_anomalies(
            records,
            baseline_days=BASELINE_DAYS,
            alert_minutes=ALERT_MINUTES,
        )

        detected_dates = {
            pd.to_datetime(a["Data"]).date()
            for a in anomalies
        }

        mean_in = baseline["entrada"]["mean"]
        mean_out = baseline["saida"]["mean"]

        # Usa os deltas já calculados pela mesma função.
        anomaly_map = {
            pd.to_datetime(a["Data"]).date(): a
            for a in anomalies
        }

        for _, row in group.iloc[BASELINE_DAYS:].iterrows():
            key = (str(employee_id), row["Data"])
            injected = truth_map.get(key, False)
            detected = row["Data"] in detected_dates

            if injected != detected:
                anomaly = anomaly_map.get(row["Data"])

                results.append(
                    {
                        "EmployeeID": employee_id,
                        "Data": row["Data"],
                        "Injected": injected,
                        "Detected": detected,
                        "Classification": (
                            "FN" if injected and not detected else "FP"
                        ),
                        "BaselineEntry": mean_in,
                        "BaselineExit": mean_out,
                        "Entrada": row["Entrada"],
                        "Saida": row["Saida"],
                        "DeltaEntrada": (
                            anomaly["DeltaEntradaMin"]
                            if anomaly else None
                        ),
                        "DeltaSaida": (
                            anomaly["DeltaSaidaMin"]
                            if anomaly else None
                        ),
                    }
                )

    errors = pd.DataFrame(results)

    print("\n=== ERROR DIAGNOSTICS ===")
    print(errors["Classification"].value_counts())

    print("\n--- SAMPLE FALSE NEGATIVES ---")
    print(
        errors[errors["Classification"] == "FN"]
        .head(10)
        .to_string(index=False)
    )

    print("\n--- SAMPLE FALSE POSITIVES ---")
    print(
        errors[errors["Classification"] == "FP"]
        .head(10)
        .to_string(index=False)
    )

    errors.to_csv(
        "evaluation/error_diagnostics.csv",
        index=False,
    )

    print(
        "\nDetailed diagnostics saved to: "
        "evaluation/error_diagnostics.csv"
    )


if __name__ == "__main__":
    main()