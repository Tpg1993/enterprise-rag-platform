"""RAGAS & DeepEval metric calculation algorithms for Context Precision, Recall, Faithfulness, and Relevancy."""

import re


def compute_context_precision(query: str, contexts: list[str]) -> float:
    """Ratio of relevant retrieved context blocks containing query terms to total context blocks."""
    if not contexts:
        return 0.0

    q_terms = set(re.findall(r"\w+", query.lower()))
    if not q_terms:
        return 1.0

    relevant_count = 0
    for ctx in contexts:
        c_terms = set(re.findall(r"\w+", ctx.lower()))
        if q_terms.intersection(c_terms):
            relevant_count += 1

    return round(relevant_count / float(len(contexts)), 4)


def compute_context_recall(ground_truth: str | None, contexts: list[str]) -> float:
    """Ratio of ground truth key terms present across retrieved context blocks."""
    if not ground_truth:
        return 1.0
    if not contexts:
        return 0.0

    gt_terms = set(re.findall(r"\w+", ground_truth.lower()))
    if not gt_terms:
        return 1.0

    all_ctx_text = " ".join(contexts).lower()
    ctx_terms = set(re.findall(r"\w+", all_ctx_text))

    overlap = gt_terms.intersection(ctx_terms)
    return round(len(overlap) / float(len(gt_terms)), 4)


def compute_faithfulness(answer: str, contexts: list[str]) -> float:
    """Hallucination detection metric measuring proportion of answer terms grounded in context."""
    if not answer:
        return 0.0
    if not contexts:
        return 0.0

    a_terms = set(re.findall(r"\w+", answer.lower()))
    # Exclude common stop words
    stop_words = {"the", "a", "an", "is", "are", "and", "or", "in", "on", "of", "to", "for", "with", "based"}
    meaningful_terms = a_terms - stop_words

    if not meaningful_terms:
        return 1.0

    all_ctx_text = " ".join(contexts).lower()
    ctx_terms = set(re.findall(r"\w+", all_ctx_text))

    grounded = meaningful_terms.intersection(ctx_terms)
    return round(len(grounded) / float(len(meaningful_terms)), 4)


def compute_answer_relevancy(query: str, answer: str) -> float:
    """Proportion of query intent terms addressed in generated answer."""
    if not query or not answer:
        return 0.0

    q_terms = set(re.findall(r"\w+", query.lower()))
    stop_words = {"what", "how", "why", "who", "where", "is", "are", "the", "a", "an"}
    meaningful_q_terms = q_terms - stop_words

    if not meaningful_q_terms:
        return 1.0

    a_terms = set(re.findall(r"\w+", answer.lower()))
    match = meaningful_q_terms.intersection(a_terms)

    return round(len(match) / float(len(meaningful_q_terms)), 4)
