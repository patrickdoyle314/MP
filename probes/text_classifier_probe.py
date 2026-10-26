"""Probe: can a text classifier trained on NCMEC's official case types beat the keyword rules?

Children only (age_group == "child"). Labels: NCMEC case types where present; target is
"endangered runaway" vs any other NCMEC label. Compares, with 5-fold stratified cross-validation:
  keyword   the runaway pattern from circumstances.py applied to the summary text
  tfidf_lr  TF-IDF word/bigram features + logistic regression
Also reports how much of the NamUs text the classifier would be applied to, since NamUs is written
differently (a domain-shift warning, not a score).

Usage: python probes/text_classifier_probe.py
"""
# ===================================================================================================
# HOW TO READ THIS FILE
# Business purpose: a feasibility test. Could a machine-learning model, trained on NCMEC's official
# case types, recognize runaways from the case text better than our keyword rules? (Answer: it scores
# well only by learning the poster template and dates, so it would not work on NamUs text.)
#
# Python ideas: scikit-learn pipelines, TF-IDF (turning text into word-weight numbers), logistic
# regression, cross-validation (testing on cases the model did not train on), precision/recall/F1.
# ===================================================================================================
import csv
import re
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline

ROOT = Path(__file__).resolve().parent.parent
# Same pattern circumstances.py uses for "Runaway / left voluntarily"
RUNAWAY = re.compile(r"\b(?:ran away|run ?away|left (?:home|the (?:home|residence|house)) (?:without|voluntarily)|"  # the same runaway rule circumstances.py uses, for a fair comparison
                     r"left voluntarily|left on (?:her|his|their) own|climbed out (?:of )?(?:a |the |her |his )?window|"
                     r"snuck out|walked away from|left (?:the |her |his )?(?:group home|foster|placement|facility|shelter))\b", re.I)


def main():
    P = [p for p in csv.DictReader(open(ROOT / "output/persons.csv", encoding="utf-8-sig"))
         if p["age_group"] == "child"]
    lab = [p for p in P if p["case_type"] and p["case_type"] != "unknown" and p["circumstances"].strip()]
    print("children:", len(P), "| with an NCMEC case type and text:", len(lab))
    print("labels:", Counter(p["case_type"] for p in lab).most_common())
    X = [re.sub(r"\[NCMEC\]", " ", p["circumstances"]) for p in lab]
    y = np.array([p["case_type"] == "endangeredRunaway" for p in lab])

    kw = np.array([bool(RUNAWAY.search(t)) for t in X])  # the keyword rule's answer for every labelled case (True = runaway)
    # 5-fold cross-validation: split the cases into 5 parts, train on 4 and test on the 5th, five times.
    # "Stratified" keeps the runaway share the same in every part.
    cv = StratifiedKFold(5, shuffle=True, random_state=0)
    # The model: TF-IDF turns each summary into numbers (how distinctive each word or word pair is), then
    # logistic regression learns which words point to "runaway". class_weight="balanced" stops the larger
    # class from dominating.
    model = make_pipeline(TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, lowercase=True),
                          LogisticRegression(max_iter=2000, class_weight="balanced"))
    prob = cross_val_predict(model, X, y, cv=cv, method="predict_proba")[:, 1]  # each case's predicted probability comes from a model that never saw that case
    pred = prob >= 0.5
    print(f"\nrunaway share among labeled children: {y.mean():.1%}")
    print(f"{'method':9s} {'precision':>9s} {'recall':>7s} {'F1':>6s} {'ROC-AUC':>8s}")
    for name, yp, sc in (("keyword", kw, None), ("tfidf_lr", pred, prob)):
        auc = f"{roc_auc_score(y, sc):.3f}" if sc is not None else "   -"
        print(f"{name:9s} {precision_score(y, yp):9.3f} {recall_score(y, yp):7.3f} {f1_score(y, yp):6.3f} {auc:>8s}")

    model.fit(X, y)
    terms = np.array(model[0].get_feature_names_out())
    coef = model[1].coef_[0]
    print("\nstrongest runaway cues:", ", ".join(terms[np.argsort(coef)[-12:]][::-1]))
    print("strongest non-runaway cues:", ", ".join(terms[np.argsort(coef)[:12]]))

    namus = [p for p in P if p["person_key"].startswith("namus") and p["circumstances"].strip()]
    upper = lambda t: sum(c.isupper() for c in t) / max(1, sum(c.isalpha() for c in t))
    print(f"\ndomain shift: NamUs child summaries {len(namus)}; mean length {np.mean([len(p['circumstances']) for p in namus]):.0f} chars "
          f"vs labeled NCMEC {np.mean([len(t) for t in X]):.0f}; all-caps share {np.mean([upper(p['circumstances']) for p in namus]):.0%} "
          f"vs {np.mean([upper(t) for t in X]):.0%}")


if __name__ == "__main__":
    main()
