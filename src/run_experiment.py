# Импорты необходимых библиотек
import json
import re
import urllib.request
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.base import clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.decomposition import TruncatedSVD
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import Normalizer, label_binarize
from sklearn.svm import LinearSVC

# Пути и параметры
ROOT = Path(__file__).resolve().parents[1]
DATA_DIR, RESULTS_DIR, FIGURES_DIR = ROOT / "data", ROOT / "results", ROOT / "figures"
DATA_PATH = DATA_DIR / "ru_reviews.csv"
DATA_URL = (
    "https://raw.githubusercontent.com/sismetanin/rureviews/master/"
    "women-clothing-accessories.3-class.balanced.csv"
)
RANDOM_STATE = 42
CLASSES = ["negative", "neutral", "positive"]
CLASS_RU = {"negative": "Негатив", "neutral": "Нейтрально", "positive": "Позитив"}


def normalize_text(value):
    text = str(value).lower().replace("ё", "е")
    text = re.sub(r"<[^>]+>|https?://\S+|www\.\S+", " ", text)
    text = re.sub(r"\d+", " NUM ", text)
    return re.sub(r"\s+", " ", text).strip()


def tfidf_word(max_features=45000):
    return TfidfVectorizer(
        lowercase=False, ngram_range=(1, 2), min_df=3, max_df=0.995,
        max_features=max_features, sublinear_tf=True,
    )


def candidates():
    # Небольшая сетка кандидатов по каждому семейству
    return {
        "Dummy": [Pipeline([("tfidf", TfidfVectorizer(max_features=1000)),
                            ("clf", DummyClassifier(strategy="stratified", random_state=RANDOM_STATE))])],
        "MultinomialNB": [
            Pipeline([("tfidf", tfidf_word()), ("clf", MultinomialNB(alpha=a))])
            for a in (0.3, 1.0)
        ],
        "LogisticRegression": [
            Pipeline([("tfidf", tfidf_word()),
                      ("clf", LogisticRegression(C=c, max_iter=1500, class_weight="balanced",
                                                 random_state=RANDOM_STATE))])
            for c in (0.5, 1.5)
        ],
        "LinearSVC": [
            Pipeline([
                ("tfidf", TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=3,
                                          max_df=0.995, max_features=60000, sublinear_tf=True)),
                ("clf", LinearSVC(C=c, class_weight="balanced", random_state=RANDOM_STATE)),
            ])
            for c in (0.5, 1.0)
        ],
        "RandomForest": [
            Pipeline([
                ("tfidf", tfidf_word(25000)),
                ("svd", TruncatedSVD(n_components=120, random_state=RANDOM_STATE)),
                ("norm", Normalizer(copy=False)),
                ("clf", RandomForestClassifier(n_estimators=180, max_depth=24, min_samples_leaf=2,
                                               class_weight="balanced_subsample", n_jobs=-1,
                                               random_state=RANDOM_STATE)),
            ])
        ],
        "MLP": [
            Pipeline([
                ("tfidf", tfidf_word(25000)),
                ("svd", TruncatedSVD(n_components=160, random_state=RANDOM_STATE)),
                ("norm", Normalizer(copy=False)),
                ("clf", MLPClassifier(hidden_layer_sizes=(64,), alpha=0.0005, batch_size=256,
                                      max_iter=25, random_state=RANDOM_STATE)),
            ])
        ],
    }


def predict_proba(model, texts):
    if hasattr(model, "predict_proba"):
        return model.predict_proba(texts)
    scores = model.decision_function(texts)
    scores = scores - scores.max(axis=1, keepdims=True)
    exp = np.exp(scores)
    return exp / exp.sum(axis=1, keepdims=True)


def evaluate(y_true, pred, proba):
    y_bin = label_binarize(y_true, classes=CLASSES)
    return {
        "accuracy": float(accuracy_score(y_true, pred)),
        "f1_macro": float(f1_score(y_true, pred, average="macro")),
        "f1_weighted": float(f1_score(y_true, pred, average="weighted")),
        "roc_auc_ovr_macro": float(roc_auc_score(y_bin, proba, average="macro", multi_class="ovr")),
        "log_loss": float(log_loss(y_true, proba, labels=CLASSES)),
    }


def main():
    for d in (DATA_DIR, RESULTS_DIR, FIGURES_DIR):
        d.mkdir(parents=True, exist_ok=True)

    # 1. Загрузка и очистка RuReviews
    if not DATA_PATH.exists():
        print("Downloading RuReviews...")
        urllib.request.urlretrieve(DATA_URL, DATA_PATH)

    raw = pd.read_csv(DATA_PATH, sep="\t", encoding="utf-8")
    raw.columns = [c.strip() for c in raw.columns]
    initial_rows = len(raw)
    data = raw.dropna(subset=["review", "sentiment"]).copy()
    missing = initial_rows - len(data)
    data["text"] = data["review"].map(normalize_text)
    data["sentiment"] = data["sentiment"].astype(str).str.strip().str.lower().replace({"neautral": "neutral"})
    invalid = int((~data["sentiment"].isin(CLASSES)).sum())
    data = data[data["sentiment"].isin(CLASSES)]
    short = int((data["text"].str.len() < 3).sum())
    data = data[data["text"].str.len() >= 3]
    duplicates = int(data.duplicated("text").sum())
    data = data.drop_duplicates("text").reset_index(drop=True)
    data["text_length"] = data["text"].str.len()

    summary = {
        "dataset": "RuReviews",
        "initial_rows": initial_rows,
        "modeling_rows": len(data),
        "class_counts": {c: int((data["sentiment"] == c).sum()) for c in CLASSES},
        "median_text_length": float(data["text_length"].median()),
        "mean_text_length": float(data["text_length"].mean()),
        "median_word_count": float(data["text"].str.split().str.len().median()),
        "short_texts_removed": short,
        "duplicate_texts_removed": duplicates,
        "missing_rows_removed": missing,
        "invalid_labels_removed": invalid,
        "source": DATA_URL,
        "license": "Apache-2.0",
        "random_state": RANDOM_STATE,
    }

    # 2. Разведочные графики
    sns.set_theme(style="whitegrid")
    counts = data["sentiment"].value_counts().reindex(CLASSES)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar([CLASS_RU[c] for c in CLASSES], counts.values, color=["#C44E52", "#DD8452", "#4C72B0"])
    ax.set_ylabel("Количество отзывов")
    ax.set_title("Распределение классов после удаления дубликатов")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "class_distribution.png", dpi=200)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    plot_df = data.assign(
        length=data["text_length"].clip(upper=data["text_length"].quantile(0.99)),
        class_ru=data["sentiment"].map(CLASS_RU),
    )
    sns.histplot(data=plot_df, x="length", hue="class_ru", bins=40, element="step",
                 stat="density", common_norm=False, ax=ax)
    ax.set_xlabel("Длина текста, символов")
    ax.set_title("Распределение длины отзывов по классам")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "text_length_distribution.png", dpi=200)
    plt.close(fig)

    # 3. Разбиение 60/20/20
    train_val, test = train_test_split(data, test_size=0.20, random_state=RANDOM_STATE, stratify=data["sentiment"])
    train, val = train_test_split(train_val, test_size=0.25, random_state=RANDOM_STATE, stratify=train_val["sentiment"])
    summary.update({"train_rows": len(train), "validation_rows": len(val), "test_rows": len(test)})
    (RESULTS_DIR / "data_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # 4. Подбор по validation и оценка на test
    selected, tuning = {}, []
    for name, models in candidates().items():
        best_f1, best_model = -1.0, None
        for i, model in enumerate(models, 1):
            model.fit(train["text"], train["sentiment"])
            f1 = f1_score(val["sentiment"], model.predict(val["text"]), average="macro")
            tuning.append({"model": name, "candidate": i, "validation_f1_macro": float(f1)})
            print(f"{name} candidate {i}: macro-F1={f1:.4f}")
            if f1 > best_f1:
                best_f1, best_model = f1, model
        selected[name] = best_model
    pd.DataFrame(tuning).to_csv(RESULTS_DIR / "hyperparameter_search.csv", index=False)

    train_val = pd.concat([train, val], ignore_index=True)
    rows, fitted = [], {}
    for name, model in selected.items():
        final = clone(model).fit(train_val["text"], train_val["sentiment"])
        pred = final.predict(test["text"])
        row = {"model": name, **evaluate(test["sentiment"], pred, predict_proba(final, test["text"]))}
        rows.append(row)
        fitted[name] = final
        print(f"Test {name}: macro-F1={row['f1_macro']:.4f}")

    metrics = pd.DataFrame(rows).sort_values("f1_macro", ascending=False)
    metrics.to_csv(RESULTS_DIR / "model_metrics.csv", index=False)
    best_name = metrics.iloc[0]["model"]
    best = fitted[best_name]

    # 5. Сравнение моделей
    long = metrics.melt(id_vars="model", value_vars=["accuracy", "f1_macro", "roc_auc_ovr_macro"],
                        var_name="metric", value_name="value")
    fig, ax = plt.subplots(figsize=(9, 4.5))
    sns.barplot(data=long, x="model", y="value", hue="metric", ax=ax)
    ax.set_ylim(0.25, 1.0)
    ax.set_title("Сравнение моделей на отложенной тестовой выборке")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "model_comparison.png", dpi=200)
    plt.close(fig)

    # 6. Матрица ошибок и отчёт
    pred = best.predict(test["text"])
    before = predict_proba(best, test["text"])
    fig, ax = plt.subplots(figsize=(6, 5))
    ConfusionMatrixDisplay.from_predictions(
        test["sentiment"], pred, labels=CLASSES,
        display_labels=[CLASS_RU[c] for c in CLASSES], cmap="Blues", colorbar=False, ax=ax,
    )
    ax.set_title(f"Матрица ошибок: {best_name}")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "confusion_matrix.png", dpi=200)
    plt.close(fig)

    report = classification_report(
        test["sentiment"], pred, labels=CLASSES,
        target_names=[CLASS_RU[c] for c in CLASSES], output_dict=True, zero_division=0,
    )
    pd.DataFrame(report).T.to_csv(RESULTS_DIR / "classification_report.csv")
    cm = confusion_matrix(test["sentiment"], pred, labels=CLASSES)
    pd.DataFrame(cm, index=CLASSES, columns=CLASSES).to_csv(RESULTS_DIR / "confusion_matrix.csv")

    # 7. Топ-признаки логистической регрессии
    if "tfidf" in best.named_steps and hasattr(best.named_steps["clf"], "coef_"):
        feats = np.asarray(best.named_steps["tfidf"].get_feature_names_out())
        coef = best.named_steps["clf"].coef_
        rows_f = []
        for i, label in enumerate(best.named_steps["clf"].classes_):
            for j in np.argsort(coef[i])[-12:]:
                rows_f.append({"class": label, "feature": feats[j], "weight": coef[i, j]})
        feat_df = pd.DataFrame(rows_f)
        feat_df.to_csv(RESULTS_DIR / "top_features.csv", index=False)
        fig, axes = plt.subplots(1, 3, figsize=(13, 5))
        for ax, label, color in zip(axes, CLASSES, ["#C44E52", "#DD8452", "#4C72B0"]):
            sub = feat_df[feat_df["class"] == label].sort_values("weight")
            ax.barh(sub["feature"], sub["weight"], color=color)
            ax.set_title(CLASS_RU[label])
        fig.suptitle(f"Наиболее значимые признаки: {best_name}")
        fig.tight_layout()
        fig.savefig(FIGURES_DIR / "top_features.png", dpi=200)
        plt.close(fig)

    # 8. Калибровка вероятностей
    calibrated = CalibratedClassifierCV(clone(best), method="sigmoid", cv=3, n_jobs=-1)
    calibrated.fit(train_val["text"], train_val["sentiment"])
    after = calibrated.predict_proba(test["text"])
    y_bin = label_binarize(test["sentiment"], classes=CLASSES)
    brier = lambda p: float(np.mean(np.sum((p - y_bin) ** 2, axis=1)))
    calibration = {
        "model": best_name,
        "multiclass_brier_before": brier(before),
        "multiclass_brier_after": brier(after),
        "log_loss_before": float(log_loss(test["sentiment"], before, labels=CLASSES)),
        "log_loss_after": float(log_loss(test["sentiment"], after, labels=CLASSES)),
    }
    (RESULTS_DIR / "calibration_metrics.json").write_text(
        json.dumps(calibration, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    for i, label in enumerate(CLASSES):
        y = (test["sentiment"].to_numpy() == label).astype(int)
        for proba, name, marker in ((before[:, i], "До калибровки", "o"), (after[:, i], "После калибровки", "s")):
            bins = pd.qcut(proba, q=10, duplicates="drop")
            g = pd.DataFrame({"p": proba, "y": y, "bin": bins}).groupby("bin", observed=True).mean()
            axes[i].plot(g["p"], g["y"], marker=marker, label=name)
        axes[i].plot([0, 1], [0, 1], "--", color="gray")
        axes[i].set_title(CLASS_RU[label])
        axes[i].legend(fontsize=8)
    fig.suptitle("Калибровочные кривые лучшей модели")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "calibration_curve.png", dpi=200)
    plt.close(fig)

    err = test.assign(prediction=pred, confidence=after.max(axis=1))
    err = err[err["sentiment"] != err["prediction"]].sort_values("confidence", ascending=False)
    err[["text", "sentiment", "prediction", "confidence"]].head(75).to_csv(
        RESULTS_DIR / "high_confidence_errors.csv", index=False
    )

    summary_out = {"best_model": best_name, "best_metrics": metrics.iloc[0].to_dict(), "calibration": calibration}
    (RESULTS_DIR / "experiment_summary.json").write_text(
        json.dumps(summary_out, ensure_ascii=False, indent=2, default=float), encoding="utf-8"
    )
    print(metrics.to_string(index=False))
    print(json.dumps(summary_out, ensure_ascii=False, indent=2, default=float))


if __name__ == "__main__":
    main()
