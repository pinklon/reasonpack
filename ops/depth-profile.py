#!/usr/bin/env python3
"""ReasonPack editorial depth policy, separate from immutable source acquisition."""

DEFAULT = "standard"
PROFILES = {
    "short": {
        "purpose": "Focused deconstruction for a narrow or thin source.",
        "requirements": [
            "Identify the central claim, decisive evidence, strongest objection and practical consequence.",
            "Use descriptive, source-specific section or timestamp labels.",
            "Flag material gaps. Do not invent breadth that the source does not support.",
        ],
    },
    "standard": {
        "purpose": "Balanced deconstruction of substantive claims and mechanisms.",
        "requirements": [
            "Map main claims and representative mechanisms to source locations and evidence roles.",
            "Distinguish reported workflow, directly observed behavior, independent corroboration and inference.",
            "Explain useful implementation choices, tradeoffs, failure modes and a GhostMesh application.",
            "Use unique, navigable, descriptive chapter labels rather than generic category repeats.",
        ],
    },
    "deep": {
        "purpose": "Extended treatment when the tooling, implementation or claims merit it.",
        "requirements": [
            "Trace the end-to-end workflow, tools, configurations, permissions, interfaces and handoffs wherever the source supports them.",
            "Explain why each consequential design choice works, what could break, and what a bounded GhostMesh adoption would require.",
            "Map all materially distinct topics to precise source cues with useful, non-repeated chapter labels.",
            "Audit self-reported outcomes against independent evidence; distinguish measurement gaps and counterexamples.",
            "Present the strongest counterargument, operational/security tradeoffs and a falsifiable adoption test.",
        ],
    },
    "exhaustive": {
        "purpose": "Evidence-led reference treatment for unusually dense or consequential material.",
        "requirements": [
            "Inventory every materially distinct demonstrated tool, configuration, workflow step and integration; mark what cannot be verified.",
            "Build a detailed source-location-to-mechanism and claim-to-evidence map, including contradictions and notable omissions.",
            "Analyze architecture, security boundaries, performance, cost, repeatability, portability and maintenance when relevant.",
            "Separate observed procedure from the creator's assertions and third-party corroboration; do not turn absence of evidence into certainty.",
            "Include alternatives, a failure-mode matrix, reproducible tests and prioritized GhostMesh adoption decisions.",
            "Give every jump point a distinct, descriptive label that says what happens there.",
        ],
    },
}


def resolve(name: str) -> dict:
    if not isinstance(name, str) or name not in PROFILES:
        raise ValueError("invalid depth profile; choose short, standard, deep or exhaustive")
    return {"name": name, **PROFILES[name]}
