import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

MODEL_DIR = "./clearconsent-distilbert-v2"

APP_CATEGORY_MAP = {
    "Covenant Not To Sue": "WAIVER_OF_RIGHTS",
    "Cap On Liability": "LIABILITY_LIMITATION",
    "Indemnification": "FINANCIAL_LIABILITY",
    "Liquidated Damages": "FINANCIAL_LIABILITY",
    "Renewal Term": "AUTO_RENEWAL",
    "Termination For Convenience": "TERMINATION",
    "Non-Compete": "EMPLOYMENT_RESTRICTION",
    "Non-Solicit Of Customers": "EMPLOYMENT_RESTRICTION",
    "Non-Solicit Of Employees": "EMPLOYMENT_RESTRICTION",
    "Insurance": "FINANCIAL_LIABILITY",
    "Governing Law": "LEGAL_JURISDICTION",
    "Warranty Duration": "LIMITED_PROTECTION",
}


def severity_from_category(category, confidence):
    critical = {
        "WAIVER_OF_RIGHTS",
        "LIABILITY_LIMITATION",
        "FINANCIAL_LIABILITY",
        "EMPLOYMENT_RESTRICTION",
    }

    if category in critical and confidence >= 0.70:
        return "CRITICAL"
    if confidence >= 0.55:
        return "HIGH"
    if confidence >= 0.40:
        return "MEDIUM"
    return "LOW"


def predict(text, threshold=0.35):
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=256,
    )

    inputs = {k: v.to(device) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.sigmoid(outputs.logits)[0]

    results = []

    for i, prob in enumerate(probs):
        confidence = float(prob)
        app_category = model.config.id2label[i]

        if confidence >= threshold:
            results.append({
                "app_type": app_category,
                "confidence": round(confidence, 5),
                "severity": severity_from_category(app_category, confidence),
            })

    results.sort(key=lambda x: x["confidence"], reverse=True)
    return results


device = "cuda" if torch.cuda.is_available() else "cpu"

tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_DIR)
model.to(device)
model.eval()

print("Device:", device)
if device == "cuda":
    print("GPU:", torch.cuda.get_device_name(0))

samples = [
    {
        "name": "Waiver / lawsuit risk",
        "text": "Patient agrees to waive the right to bring a lawsuit in court and releases the hospital from all claims related to treatment."
    },
    {
        "name": "Arbitration-style risk",
        "text": "Any dispute arising from this agreement shall be resolved through binding arbitration and not through a jury trial."
    },
    {
        "name": "Financial liability",
        "text": "The patient accepts full financial responsibility for any charges, fees, or balances not covered by insurance."
    },
    {
        "name": "Auto renewal",
        "text": "This agreement will automatically renew for successive one-year terms unless either party gives written notice of cancellation."
    },
    {
        "name": "Safe normal sentence",
        "text": "The user may contact support during regular business hours to ask questions about the service."
    },
]

for sample in samples:
    print("\n" + "=" * 80)
    print(sample["name"])
    print(sample["text"])
    print("Predictions:")
    preds = predict(sample["text"], threshold=0.30)

    if not preds:
        print("No risky clauses detected.")
    else:
        for pred in preds:
            print(pred)