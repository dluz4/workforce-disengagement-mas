import pandas as pd

from src.analytics import compute_baseline_and_anomalies


EXCEL_PATH = "Time_2025_Q1_Q3_fake_Python.xlsx"
BASELINE_DAYS = 30
ALERT_MINUTES = 30


def main():
    registros = pd.read_excel(EXCEL_PATH, sheet_name="Registros")
    ground_truth = pd.read_excel(EXCEL_PATH, sheet_name="GroundTruth")

    # Normaliza as datas para permitir comparação segura.
    registros["Data"] = pd.to_datetime(registros["Data"]).dt.date
    ground_truth["Data"] = pd.to_datetime(ground_truth["Data"]).dt.date

    # Conjunto das observações que receberam uma alteração sintética.
    injected = set(
        zip(
            ground_truth.loc[
                ground_truth["InjectedDeviation"] == True, "EmployeeID"
            ].astype(str),
            ground_truth.loc[
                ground_truth["InjectedDeviation"] == True, "Data"
            ],
        )
    )

    detected = set()

    # Executa exatamente a mesma lógica usada pelo MAS.
    for employee_id, group in registros.groupby("EmployeeID"):
        group = group.sort_values("Data")

        records = group[
            ["EmployeeID", "Data", "Entrada", "Saida"]
        ].to_dict("records")

        _, anomalies = compute_baseline_and_anomalies(
            records,
            baseline_days=BASELINE_DAYS,
            alert_minutes=ALERT_MINUTES,
        )

        for anomaly in anomalies:
            detected.add(
                (
                    str(employee_id),
                    pd.to_datetime(anomaly["Data"]).date(),
                )
            )

    # Universo avaliado = somente observações pós-baseline.
    evaluated = set()

    for employee_id, group in registros.groupby("EmployeeID"):
        group = group.sort_values("Data").iloc[BASELINE_DAYS:]

        for _, row in group.iterrows():
            evaluated.add(
                (
                    str(employee_id),
                    row["Data"],
                )
            )

    # Matriz de confusão.
    tp = len(detected & injected)
    fp = len(detected - injected)
    fn = len(injected - detected)
    tn = len(evaluated - detected - injected)

    precision = tp / (tp + fp) if (tp + fp) else 0
    recall = tp / (tp + fn) if (tp + fn) else 0

    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0
    )

    print("\n=== GROUND-TRUTH EVALUATION ===")
    print(f"Post-baseline observations: {len(evaluated)}")
    print(f"Injected deviations: {len(injected)}")
    print(f"Detected anomalies: {len(detected)}")

    print("\n--- Confusion Matrix ---")
    print(f"TP: {tp}")
    print(f"FP: {fp}")
    print(f"FN: {fn}")
    print(f"TN: {tn}")

    print("\n--- Detection Performance ---")
    print(f"Precision: {precision:.4f} ({precision:.2%})")
    print(f"Recall:    {recall:.4f} ({recall:.2%})")
    print(f"F1-score:  {f1:.4f} ({f1:.2%})")


if __name__ == "__main__":
    main()