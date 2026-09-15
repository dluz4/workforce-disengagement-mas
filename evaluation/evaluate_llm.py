import os
import time

import pandas as pd
from openai import OpenAI

from src.analytics import compute_baseline_and_anomalies


EXCEL_PATH = "Time_2025_Q1_Q3_fake_Python.xlsx"
MODEL = "gpt-4o-mini"
TEMPERATURE = 0.7
BASELINE_DAYS = 30
ALERT_MINUTES = 30

SYSTEM_PROMPT = (
                "You are an HR support agent that writes concise and fair messages."
            )

# Current GPT-4o mini API prices per 1M tokens.
INPUT_PRICE_PER_MILLION = 0.15
OUTPUT_PRICE_PER_MILLION = 0.60


def build_prompt(
    employee_id,
    managerial_position,
    priority,
    anomaly_count,
    sample_anomalies,
):
    def describe_delta(delta, event):
        delta = float(delta)

        if event == "clock-in":
            if delta > 0:
                return f"{abs(delta):.0f} minutes later than individual baseline"
            elif delta < 0:
                return f"{abs(delta):.0f} minutes earlier than individual baseline"

        if event == "clock-out":
            if delta > 0:
                return f"{abs(delta):.0f} minutes later than individual baseline"
            elif delta < 0:
                return f"{abs(delta):.0f} minutes earlier than individual baseline"

        return "aligned with individual baseline"


    formatted_examples = []

    for anomaly in sample_anomalies:
        formatted_examples.append(
            {
                "Date": anomaly["Data"],
                "Clock-in": anomaly["Entrada"],
                "Clock-in deviation": describe_delta(
                    anomaly["DeltaEntradaMin"],
                    "clock-in",
                ),
                "Clock-out": anomaly["Saida"],
                "Clock-out deviation": describe_delta(
                    anomaly["DeltaSaidaMin"],
                    "clock-out",
                ),
            }
        )


    technical_alert = (
        f"Employee {employee_id} presented {anomaly_count} attendance "
        f"observations exceeding the individual >{ALERT_MINUTES}-minute "
        "temporal deviation threshold.\n"
        "The deviations below are already interpreted relative to the "
        "employee's individual baseline. Do not reverse or reinterpret "
        "the direction of the deviations.\n"
        f"Examples: {formatted_examples}"
    )

    prompt = (
        "You are an HR support agent.\n"
        "Transform a technical attendance alert into a short, "
        "clear and fair explanation for an HR Partner.\n\n"
        "Rules:\n"
        "- Do not accuse the employee.\n"
        "- Do not diagnose disengagement or a health condition.\n"
        "- Describe the information as a behavioral signal "
        "requiring contextual validation.\n"
        "- Recommend human review and validation.\n"
        "- Do not infer causes such as disengagement, workload, wellbeing, "
        "performance, or health from attendance data alone.\n"
        "- Preserve the stated direction of each temporal deviation "
        "(earlier/later) exactly as provided.\n"
        "- State that contextual factors such as schedule changes, "
        "approved arrangements, operational requirements, or data-quality "
        "issues should be considered during human review.\n"
        "- Be concise.\n\n"
        f"EmployeeID={employee_id}\n"
        f"ManagerialPosition={managerial_position}\n"
        f"Priority={priority}\n\n"
        "TECHNICAL ALERT:\n"
        f"{technical_alert}\n\n"
        "Write the message for the HR Partner."
    )

    return technical_alert, prompt


def main():
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    registros = pd.read_excel(EXCEL_PATH, sheet_name="Registros")
    funcionarios = pd.read_excel(EXCEL_PATH, sheet_name="Funcionarios")

    position_map = dict(
        zip(
            funcionarios["EmployeeID"].astype(str),
            funcionarios["PosGerencial"].astype(str),
        )
    )

    candidates = []

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

        if not anomalies:
            continue

        position = position_map.get(str(employee_id), "NaoGerente")
        priority = (
            "HIGH"
            if position.strip().lower() == "gerente"
            else "NORMAL"
        )

        candidates.append(
            {
                "EmployeeID": str(employee_id),
                "Position": position,
                "Priority": priority,
                "AnomalyCount": len(anomalies),
                "Anomalies": anomalies,
            }
        )

    # Deterministic selection:
    # two HIGH and two NORMAL cases with the largest anomaly counts.
    high = sorted(
        [x for x in candidates if x["Priority"] == "HIGH"],
        key=lambda x: (-x["AnomalyCount"], x["EmployeeID"]),
    )[:2]

    normal = sorted(
        [x for x in candidates if x["Priority"] == "NORMAL"],
        key=lambda x: (-x["AnomalyCount"], x["EmployeeID"]),
    )[:2]

    selected = high + normal

    print("\n=== LLM END-TO-END EVALUATION ===")
    print(f"Selected cases: {len(selected)}")

    total_cost = 0.0

    results = []

    for case in selected:
        sample = case["Anomalies"][:3]

        technical_alert, prompt = build_prompt(
            case["EmployeeID"],
            case["Position"],
            case["Priority"],
            case["AnomalyCount"],
            sample,
        )

        start = time.perf_counter()

        response = client.responses.create(
            model=MODEL,
            temperature=TEMPERATURE,
            
            input=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
        )

        latency = time.perf_counter() - start

        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        total_tokens = response.usage.total_tokens

        cost = (
            input_tokens / 1_000_000 * INPUT_PRICE_PER_MILLION
            + output_tokens / 1_000_000 * OUTPUT_PRICE_PER_MILLION
        )

        total_cost += cost



        results.append(
            {
                "EmployeeID": case["EmployeeID"],
                "ManagerialPosition": case["Position"],
                "Priority": case["Priority"],
                "DetectedAnomalies": case["AnomalyCount"],
                "SystemPrompt": SYSTEM_PROMPT,
                "UserPrompt": prompt,
                "TechnicalAlert": technical_alert,
                "Model": response.model,
                "Temperature": TEMPERATURE,
                "InputTokens": input_tokens,
                "OutputTokens": output_tokens,
                "TotalTokens": total_tokens,
                "LatencySeconds": round(latency, 3),
                "EstimatedCostUSD": cost,
                "GPTResponse": response.output_text.strip(),
            }
        )





        print("\n" + "=" * 70)
        print(f"Employee: {case['EmployeeID']}")
        print(f"Position: {case['Position']}")
        print(f"Priority: {case['Priority']}")
        print(f"Detected anomalies: {case['AnomalyCount']}")

        print("\n--- TECHNICAL ALERT ---")
        print(technical_alert)

        print("\n--- LLM PARAMETERS ---")
        print(f"Model: {response.model}")
        print(f"Temperature: {TEMPERATURE}")
        print(f"Input tokens: {input_tokens}")
        print(f"Output tokens: {output_tokens}")
        print(f"Total tokens: {total_tokens}")
        print(f"Latency: {latency:.3f} seconds")
        print(f"Estimated cost: ${cost:.8f}")

        print("\n--- GPT RESPONSE ---")
        print(response.output_text.strip())

    print("\n" + "=" * 70)
    print(f"TOTAL ESTIMATED COST: ${total_cost:.8f}")





    output_path = "evaluation/llm_evaluation_results.csv"

    results_df = pd.DataFrame(results)

    results_df.to_csv(
        output_path,
        index=False,
        encoding="utf-8-sig",
    )

    print("\n--- EXPERIMENT SUMMARY ---")
    print(f"LLM calls: {len(results_df)}")
    print(f"Total tokens: {results_df['TotalTokens'].sum()}")
    print(
        f"Average latency: "
        f"{results_df['LatencySeconds'].mean():.3f} seconds"
    )
    print(
        f"Total estimated cost: $"
        f"{results_df['EstimatedCostUSD'].sum():.8f}"
    )
    print(f"Results saved to: {output_path}")



if __name__ == "__main__":
    main()