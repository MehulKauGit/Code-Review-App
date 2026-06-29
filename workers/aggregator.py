from collections import OrderedDict

def aggregate_findings(*finding_lists: list[dict]) -> dict:
    all_findings = [f for findings in finding_lists for f in findings]
    deduped: OrderedDict[tuple, dict] = OrderedDict()

    for finding in all_findings:
        key = (finding["file"], finding["line"], finding["severity"])
        if key in deduped:
            existing_sources = deduped[key]["source"]
            if isinstance(existing_sources, str):
                existing_sources = [existing_sources]
            if finding["source"] not in existing_sources:
                deduped[key]["source"] = existing_sources + [finding["source"]]
        else:
            deduped[key] = dict(finding)

    findings = list(deduped.values())
    summary = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for f in findings:
        summary[f["severity"]] += 1

    return {
        "findings": findings,
        "summary": summary,
        "total": len(findings),
    }