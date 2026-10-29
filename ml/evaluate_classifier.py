import os
import json
import sys

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from api.classifier import classifier
except ImportError:
    from backend.classifier import classifier
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
from tabulate import tabulate

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def run_evaluation():
    dataset_path = os.path.join(os.path.dirname(__file__), "route_classifier_test_set.json")
    with open(dataset_path, "r") as f:
        test_cases = json.load(f)

    y_true = []
    y_pred = []
    labels = ["RTI", "Rights/Grievance", "Other"]

    print(f"\n==========================================")
    print(f"  CivicRoute Route Classifier Evaluation  ")
    print(f"==========================================\n")
    print(f"Evaluating on {len(test_cases)} labeled examples...\n")

    for i, item in enumerate(test_cases, 1):
        text = item["text"]
        expected = item["expected"]
        result = classifier.classify(text)
        predicted = result["route"]

        y_true.append(expected)
        y_pred.append(predicted)

        match = "✓" if predicted == expected else "✗"
        print(f"[{match}] Case {i:02d}: Expected='{expected}' | Predicted='{predicted}' ({result['confidence']:.2f})")

    acc = accuracy_score(y_true, y_pred)
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    report = classification_report(y_true, y_pred, labels=labels, target_names=labels, zero_division=0)

    print("\n------------------------------------------")
    print(f"Overall Accuracy: {acc * 100:.2f}%")
    print("------------------------------------------\n")
    print("Detailed Classification Report:\n")
    print(report)

    print("Confusion Matrix:")
    cm_table = []
    for i, row in enumerate(cm):
        cm_table.append([f"Actual {labels[i]}"] + list(row))
    headers = [""] + [f"Pred {lbl}" for lbl in labels]
    print(tabulate(cm_table, headers=headers, tablefmt="grid"))
    print("\n")

if __name__ == "__main__":
    run_evaluation()
