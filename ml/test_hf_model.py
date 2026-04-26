import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

HF_MODEL_ID = "1Ghoul1/clearconsent-distilbert-v2"

samples = [
    ("Waiver", "Patient agrees to waive the right to bring a lawsuit and releases the clinic from all claims."),
    ("Arbitration", "Any dispute shall be resolved through binding arbitration and not through a jury trial."),
    ("Financial", "The patient accepts full financial responsibility for charges not covered by insurance."),
    ("Renewal", "This agreement will automatically renew for successive one-year terms unless cancelled in writing."),
    ("Liability limit", "The company's total liability shall not exceed the amount paid under this agreement."),
    ("Safe", "The patient may ask questions before signing and may request a copy of this form."),
]

tokenizer = AutoTokenizer.from_pretrained(HF_MODEL_ID)
model = AutoModelForSequenceClassification.from_pretrained(HF_MODEL_ID)
model.eval()

for name, text in samples:
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True, max_length=256)

    with torch.no_grad():
        outputs = model(**inputs)
        probs = torch.sigmoid(outputs.logits)[0]

    preds = []
    for i, prob in enumerate(probs):
        confidence = float(prob)
        if confidence >= 0.30:
            preds.append((model.config.id2label[i], round(confidence, 4)))

    preds.sort(key=lambda x: x[1], reverse=True)

    print("\n" + "=" * 80)
    print(name)
    print(text)
    print(preds if preds else "No risky clauses detected")