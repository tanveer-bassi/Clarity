import os
import re
import json
import random
import numpy as np
import torch

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "0"

from datasets import load_dataset, Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
)
from sklearn.metrics import f1_score, precision_score, recall_score


MODEL_NAME = "distilbert-base-uncased"
OUTPUT_DIR = "./clearconsent-distilbert-v2"

TARGET_LABELS = [
    "WAIVER_OF_RIGHTS",
    "ARBITRATION",
    "LIABILITY_LIMITATION",
    "FINANCIAL_LIABILITY",
    "AUTO_RENEWAL",
    "TERMINATION",
    "EMPLOYMENT_RESTRICTION",
    "LEGAL_JURISDICTION",
    "LIMITED_PROTECTION",
]


CUAD_TO_APP_LABEL = {
    "Covenant Not To Sue": "WAIVER_OF_RIGHTS",
    "Cap On Liability": "LIABILITY_LIMITATION",
    "Indemnification": "FINANCIAL_LIABILITY",
    "Liquidated Damages": "FINANCIAL_LIABILITY",
    "Insurance": "FINANCIAL_LIABILITY",
    "Renewal Term": "AUTO_RENEWAL",
    "Termination For Convenience": "TERMINATION",
    "Non-Compete": "EMPLOYMENT_RESTRICTION",
    "Non-Solicit Of Customers": "EMPLOYMENT_RESTRICTION",
    "Non-Solicit Of Employees": "EMPLOYMENT_RESTRICTION",
    "Governing Law": "LEGAL_JURISDICTION",
    "Warranty Duration": "LIMITED_PROTECTION",
}

CUAD_SOURCE_LABELS = list(CUAD_TO_APP_LABEL.keys())

label2id = {label: i for i, label in enumerate(TARGET_LABELS)}
id2label = {i: label for label, i in label2id.items()}


def clean_text(text: str) -> str:
    text = str(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def chunk_text(text: str, max_words: int = 180):
    text = clean_text(text)
    parts = re.split(r"(?<=[.;])\s+|(?:\n\s*\d+[\.\)]\s*)", text)
    parts = [clean_text(p) for p in parts if len(clean_text(p)) > 40]

    chunks = []
    current = []

    for part in parts:
        words = part.split()
        if len(current) + len(words) <= max_words:
            current.extend(words)
        else:
            if current:
                chunks.append(" ".join(current))
            current = words

    if current:
        chunks.append(" ".join(current))

    return chunks

def make_example(text, app_label):
    labels = [0.0] * len(TARGET_LABELS)
    labels[label2id[app_label]] = 1.0
    return {
        "text": clean_text(text),
        "labels": labels,
    }


def build_synthetic_examples():
    examples = []

    waiver_texts = [
        "Patient agrees to waive the right to bring a lawsuit in court for any claims related to treatment.",
        "By signing this agreement, the signer releases the company from all claims, damages, and legal actions.",
        "The participant waives any right to sue the organization for injuries, losses, or damages arising from participation.",
        "You agree not to bring any legal action against the provider, its employees, or its affiliates.",
        "The signer releases and forever discharges the institution from liability for any claim related to this agreement.",
        "You give up your right to pursue legal claims against the company except where prohibited by law.",
        "The patient waives the right to trial by jury and agrees not to sue the hospital for ordinary negligence.",
        "The user releases the service provider from any and all claims connected to the use of the service.",
    ]

    arbitration_texts = [
        "Any dispute arising from this agreement shall be resolved through binding arbitration.",
        "The parties agree that all claims must be submitted to an arbitrator instead of a court.",
        "You waive the right to a jury trial and agree to resolve disputes by private arbitration.",
        "All disputes shall be handled by binding arbitration under the rules of the arbitration association.",
        "The signer agrees that arbitration is the exclusive method for resolving any claim or controversy.",
        "Any controversy or claim arising out of this contract shall be settled by arbitration.",
        "You may not bring a class action and must resolve disputes through individual arbitration.",
        "Claims related to this agreement will be decided by an arbitrator and not by a judge or jury.",
    ]

    liability_texts = [
        "The company's total liability shall not exceed the amount paid under this agreement.",
        "In no event shall the provider be liable for indirect, incidental, special, or consequential damages.",
        "The hospital is not responsible for losses, damages, or complications except as required by law.",
        "Liability is limited to direct damages and shall not exceed one hundred dollars.",
        "The provider disclaims all liability for damages arising from use of the service.",
    ]

    financial_texts = [
        "The patient accepts full financial responsibility for any charges not covered by insurance.",
        "You are responsible for all unpaid balances, deductibles, fees, and out-of-network costs.",
        "The guarantor agrees to pay any amount that insurance refuses to cover.",
        "The signer shall indemnify and hold harmless the company from all losses and expenses.",
        "You agree to reimburse the provider for costs, claims, damages, and attorney fees.",
    ]

    renewal_texts = [
        "This agreement will automatically renew for successive one-year terms unless cancelled in writing.",
        "The subscription renews automatically unless notice of cancellation is provided thirty days before renewal.",
        "The contract shall renew for additional terms unless either party gives written notice.",
        "Your membership will continue and you will be charged unless you cancel before the renewal date.",
    ]

    termination_texts = [
        "The company may terminate this agreement at any time without notice.",
        "The provider may suspend or terminate access immediately for any reason.",
        "Either party may terminate this agreement for convenience upon written notice.",
        "The institution may end services without prior notice or liability.",
    ]

    employment_texts = [
        "Employee agrees not to compete with the company for one year after termination.",
        "The contractor shall not solicit customers or employees of the company after the agreement ends.",
        "You may not work for a competing business during the restricted period.",
        "The employee agrees to a non-compete and non-solicitation restriction after employment.",
    ]

    safe_texts = [
        "The user may contact support during regular business hours to ask questions about the service.",
        "This document explains the general process and provides contact information for assistance.",
        "The signer may request a copy of this agreement for personal records.",
        "The company will provide updates by email when the service changes.",
        "The patient may ask questions before signing this form.",
        "You can cancel your appointment by contacting the office.",
    ]

    for text in waiver_texts:
        examples.append(make_example(text, "WAIVER_OF_RIGHTS"))

    for text in arbitration_texts:
        examples.append(make_example(text, "ARBITRATION"))

    for text in liability_texts:
        examples.append(make_example(text, "LIABILITY_LIMITATION"))

    for text in financial_texts:
        examples.append(make_example(text, "FINANCIAL_LIABILITY"))

    for text in renewal_texts:
        examples.append(make_example(text, "AUTO_RENEWAL"))

    for text in termination_texts:
        examples.append(make_example(text, "TERMINATION"))

    for text in employment_texts:
        examples.append(make_example(text, "EMPLOYMENT_RESTRICTION"))

    # Add safe examples as true negatives.
    for text in safe_texts:
        examples.append({
            "text": clean_text(text),
            "labels": [0.0] * len(TARGET_LABELS),
        })

    return examples

def extract_examples_from_cuad():
    print("Loading CUAD dataset...")
    dataset = load_dataset("theatticusproject/cuad-qa", trust_remote_code=True)

    print(dataset)

    split_name = "train" if "train" in dataset else list(dataset.keys())[0]

    print("Dataset columns:", dataset[split_name].column_names)
    print("First row keys:", dataset[split_name][0].keys())

    positive_examples = []
    negative_candidates = []
    seen_positive = set()

    for idx, row in enumerate(dataset[split_name]):
        question = str(row.get("question", ""))
        context = clean_text(row.get("context", ""))
        answers = row.get("answers", {})

        matched_cuad_label = None

        for cuad_label in CUAD_SOURCE_LABELS:
            normalized_label = cuad_label.lower().replace("_", " ")
            normalized_question = question.lower().replace("_", " ")

            if normalized_label in normalized_question:
                matched_cuad_label = cuad_label
                break

        if not matched_cuad_label:
            continue

        app_label = CUAD_TO_APP_LABEL[matched_cuad_label]

        answer_texts = []

        if isinstance(answers, dict):
            answer_texts = answers.get("text", [])
        elif isinstance(answers, list):
            answer_texts = answers

        if isinstance(answer_texts, str):
            answer_texts = [answer_texts]

        for ans in answer_texts:
            ans = clean_text(ans)

            if len(ans) < 30:
                continue

            key = (app_label, ans[:200])

            if key in seen_positive:
                continue

            seen_positive.add(key)

            labels = [0.0] * len(TARGET_LABELS)
            labels[label2id[app_label]] = 1.0

            positive_examples.append({
                "text": ans,
                "labels": labels,
            })

        if context and idx % 20 == 0:
            chunks = chunk_text(context, max_words=120)
            random.shuffle(chunks)

            for chunk in chunks[:1]:
                if len(chunk) > 80:
                    negative_candidates.append({
                        "text": chunk,
                        "labels": [0.0] * len(TARGET_LABELS),
                    })

    synthetic_examples = build_synthetic_examples()
    positive_examples.extend(synthetic_examples)

    random.shuffle(negative_candidates)

    # Use more negatives than before, but not a crazy amount.
    max_negatives = min(len(negative_candidates), int(len(positive_examples) * 0.75))
    negative_examples = negative_candidates[:max_negatives]

    examples = positive_examples + negative_examples
    random.shuffle(examples)

    print(f"Built {len(examples)} training examples.")
    print(f"Positive examples: {len(positive_examples)}")
    print(f"Negative examples: {len(negative_examples)}")

    if len(positive_examples) < 100:
        raise RuntimeError("Too few positive examples were created. We need to adjust label matching.")

    return examples

def tokenize_batch(batch):
    return tokenizer(
        batch["text"],
        truncation=True,
        padding="max_length",
        max_length=256,
    )


def compute_metrics(eval_pred):
    logits, labels = eval_pred
    probs = 1 / (1 + np.exp(-logits))
    preds = (probs >= 0.5).astype(int)

    return {
        "micro_f1": f1_score(labels, preds, average="micro", zero_division=0),
        "macro_f1": f1_score(labels, preds, average="macro", zero_division=0),
        "precision": precision_score(labels, preds, average="micro", zero_division=0),
        "recall": recall_score(labels, preds, average="micro", zero_division=0),
    }


if __name__ == "__main__":
    random.seed(42)
    np.random.seed(42)
    torch.manual_seed(42)

    print("CUDA available:", torch.cuda.is_available())
    if torch.cuda.is_available():
        print("GPU:", torch.cuda.get_device_name(0))

    examples = extract_examples_from_cuad()
    random.shuffle(examples)

    split_idx = int(0.85 * len(examples))
    train_examples = examples[:split_idx]
    val_examples = examples[split_idx:]

    train_ds = Dataset.from_list(train_examples)
    val_ds = Dataset.from_list(val_examples)

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

    train_ds = train_ds.map(tokenize_batch, batched=True)
    val_ds = val_ds.map(tokenize_batch, batched=True)

    train_ds.set_format(
        type="torch",
        columns=["input_ids", "attention_mask", "labels"],
    )
    val_ds.set_format(
        type="torch",
        columns=["input_ids", "attention_mask", "labels"],
    )

    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        num_labels=len(TARGET_LABELS),
        id2label=id2label,
        label2id=label2id,
        problem_type="multi_label_classification",
    )

    training_args = TrainingArguments(
        output_dir=OUTPUT_DIR,
        eval_strategy="epoch",
        save_strategy="epoch",
        learning_rate=2e-5,
        per_device_train_batch_size=16,
        per_device_eval_batch_size=16,
        num_train_epochs=5,
        weight_decay=0.01,
        logging_steps=25,
        load_best_model_at_end=True,
        metric_for_best_model="micro_f1",
        fp16=True,
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        compute_metrics=compute_metrics,
    )

    trainer.train()

    print("Saving model...")
    trainer.save_model(OUTPUT_DIR)
    tokenizer.save_pretrained(OUTPUT_DIR)

    with open(os.path.join(OUTPUT_DIR, "clearconsent_labels.json"), "w") as f:
        json.dump(
            {
                "target_labels": TARGET_LABELS,
                "label2id": label2id,
                "id2label": id2label,
            },
            f,
            indent=2,
        )

    print(f"Done. Model saved to {OUTPUT_DIR}")