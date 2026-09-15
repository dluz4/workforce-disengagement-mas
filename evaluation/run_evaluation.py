from pathlib import Path

import pandas as pd

from src.analytics import compute_baseline_and_anomalies
from src.agents.priority_assessment import PriorityAssessmentAgent


EXCEL_PATH = Path("Time_2025_Q1_Q3_fake_Python.xlsx")
ATTENDANCE_SHEET = "Registros"
EMPLOYEE_SHEET = "Funcionarios"

BASELINE_DAYS = 30
ALERT_MINUTES = 30


def run_dataset_evaluation():
    attendance = pd.read_excel(
        EXCEL_PATH,
        sheet_name=ATTENDANCE_SHEET,
    )

    employees = pd.read_excel(
        EXCEL_PATH,
        sheet_name=EMPLOYEE_SHEET,
    )

    position_map = dict(
        zip(
            employees["EmployeeID"].astype(str),
            employees["PosGerencial"].astype(str),
        )
    )

    results = []

    for employee_id, group in attendance.groupby("EmployeeID"):
        employee_id = str(employee_id)

        group = group.sort_values("Data")

        records = group[
            ["EmployeeID", "Data", "Entrada", "Saida"]
        ].to_dict(orient="records")

        if len(records) <= BASELINE_DAYS:
            continue

        baseline, anomalies = compute_baseline_and_anomalies(
            records=records,
            baseline_days=BASELINE_DAYS,
            alert_minutes=ALERT_MINUTES,
        )

        position = position_map.get(
            employee_id,
            "NaoGerente",
        )

        priority = (
            PriorityAssessmentAgent.classify_priority(position)
            if anomalies
            else "NONE"
        )

        post_baseline_records = (
            len(records) - BASELINE_DAYS
        )

        results.append(
            {
                "EmployeeID": employee_id,
                "PosGerencial": position,
                "Priority": priority,
                "TotalRecords": len(records),
                "BaselineRecords": BASELINE_DAYS,
                "PostBaselineRecords": post_baseline_records,
                "BaselineEntry": baseline["entrada"]["mean"],
                "BaselineExit": baseline["saida"]["mean"],
                "Anomalies": len(anomalies),
                "HasAnomaly": len(anomalies) > 0,
            }
        )

    results_df = pd.DataFrame(results)

    total_records = len(attendance)

    baseline_records = (
        len(results_df) * BASELINE_DAYS
    )

    evaluated_records = int(
        results_df["PostBaselineRecords"].sum()
    )

    total_anomalies = int(
        results_df["Anomalies"].sum()
    )

    employees_with_anomalies = int(
        results_df["HasAnomaly"].sum()
    )

    anomaly_rate = (
        total_anomalies / evaluated_records * 100
        if evaluated_records
        else 0
    )

    high_employees = int(
        (
            (results_df["Priority"] == "HIGH")
            & results_df["HasAnomaly"]
        ).sum()
    )

    normal_employees = int(
        (
            (results_df["Priority"] == "NORMAL")
            & results_df["HasAnomaly"]
        ).sum()
    )

    print("\n=== DATASET EXPERIMENTAL EVALUATION ===")

    print(f"Dataset: {EXCEL_PATH.name}")
    print(f"Employees: {len(results_df)}")
    print(f"Total attendance records: {total_records}")

    print(
        f"Baseline records: {baseline_records}"
    )

    print(
        f"Post-baseline records evaluated: "
        f"{evaluated_records}"
    )

    print(
        f"Baseline per employee: "
        f"{BASELINE_DAYS} records"
    )

    print(
        f"Alert threshold: "
        f">{ALERT_MINUTES} minutes"
    )

    print(
        f"Employees with anomalies: "
        f"{employees_with_anomalies}"
    )

    print(
        f"Employees without anomalies: "
        f"{len(results_df) - employees_with_anomalies}"
    )

    print(
        f"Total anomalies detected: "
        f"{total_anomalies}"
    )

    print(
        f"Post-baseline anomaly rate: "
        f"{anomaly_rate:.2f}%"
    )

    print(
        f"Employees with HIGH priority: "
        f"{high_employees}"
    )

    print(
        f"Employees with NORMAL priority: "
        f"{normal_employees}"
    )

    print("\n--- By managerial position ---")

    summary = (
        results_df
        .groupby("PosGerencial")
        .agg(
            Employees=("EmployeeID", "count"),
            EmployeesWithAnomaly=("HasAnomaly", "sum"),
            TotalAnomalies=("Anomalies", "sum"),
        )
    )

    print(summary)

    results_df.to_csv(
        "evaluation/evaluation_results.csv",
        index=False,
    )

    print(
        "\nDetailed results saved to: "
        "evaluation/evaluation_results.csv"
    )

    return results_df


if __name__ == "__main__":
    run_dataset_evaluation()