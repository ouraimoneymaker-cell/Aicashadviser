from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple

from evidence import sha256_bytes, sha256_text
from verizon_structurer import structure_verizon_pdf_bytes

# -----------------------------
# Guardrails (deterministic)
# -----------------------------
# Verizon bills will never legitimately contain billion-dollar line items.
# This prevents OCR/parse accidents (e.g., Agreement IDs) from poisoning totals.
_MAX_REASONABLE_ABS_AMOUNT = Decimal("100000.00")

# Lines/labels that are identifiers/metadata, not billable charges
_NON_CHARGE_DESC_RE = re.compile(r"\b(agreement|remaining)\b", re.IGNORECASE)

# Promo term marker (used for continuity/gap checks)
_PROMO_TERM_RE = re.compile(r"\b(\d{1,2})\s+of\s+(\d{2})\b", re.IGNORECASE)


# -----------------------------
# Small deterministic helpers
# -----------------------------
def _safe_decimal(s: Optional[str]) -> Optional[Decimal]:
    if s is None:
        return None
    try:
        d = Decimal(str(s)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None

    # Hard clamp: deterministic fail-closed protection against OCR/ID-as-money.
    if d.copy_abs() > _MAX_REASONABLE_ABS_AMOUNT:
        return None

    return d


def _parse_iso_date(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        # "YYYY-MM-DD"
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _stable_case_id(file_hashes: List[str]) -> str:
    key = "|".join(sorted(file_hashes))
    return "case_" + sha256_text(key)[:16]


def _statement_key(header: Dict[str, Any], file_hash: str) -> str:
    inv = (header.get("invoice_number") or "").strip()
    bp = header.get("billing_period") or {}
    start = (bp.get("start") or "").strip()
    end = (bp.get("end") or "").strip()
    total_due = (header.get("total_due") or "").strip()

    # Best key: invoice + period + total due (falls back to file hash)
    if inv or (start and end) or total_due:
        return f"inv={inv}|start={start}|end={end}|total={total_due}"
    return f"file={file_hash}"


def _findings_sort_key(f: Dict[str, Any]) -> str:
    return str(f.get("id") or "")


def _should_ignore_ledger_item(it: Dict[str, Any]) -> bool:
    """
    Deterministic filter to prevent identifier-like lines from being treated as charges.
    Intended to block OCR/parse accidents like:
      description: "Agreement"
      amount: "1787272274.00"  (really an ID)
    """
    desc = str(it.get("description") or it.get("line") or "").strip()
    if not desc:
        return False

    if _NON_CHARGE_DESC_RE.search(desc):
        # If it *also* has an implausible amount, drop it.
        amt = _safe_decimal(it.get("amount"))
        if amt is None:
            # Either unparsable or beyond reasonable bounds -> ignore
            return True
        # Even if within bounds, "Agreement"/"remaining" are not charge rows
        return True

    return False


def _zero_summary_rollup(line_id: str) -> Dict[str, Any]:
    return {
        "line_id": None if line_id == "account" else line_id,
        "reconnect_fee_total": "0.00",
        "other_fee_total": "0.00",
        "fees_non_tax_total": "0.00",
        "credits_total": "0.00",
    }


def _safe_sum_money_str(a: str, b: str) -> str:
    da = _safe_decimal(a) or Decimal("0.00")
    db = _safe_decimal(b) or Decimal("0.00")
    return str((da + db).quantize(Decimal("0.01")))


def _normalize_summary_line_id(v: Any) -> str:
    # verizon_structurer uses None for "account" in summary.by_line
    if v is None:
        return "account"
    s = str(v).strip()
    return s if s else "account"


def _promo_term_numbers(it: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    pt = it.get("promo_term")
    if isinstance(pt, dict):
        cur = pt.get("current")
        tot = pt.get("total")
        cur_i: Optional[int] = None
        tot_i: Optional[int] = None
        try:
            if cur is not None:
                cur_i = int(str(cur).strip())
        except Exception:
            cur_i = None
        try:
            if tot is not None:
                tot_i = int(str(tot).strip())
        except Exception:
            tot_i = None
        if cur_i is not None or tot_i is not None:
            return cur_i, tot_i

    desc = str(it.get("description") or "")
    m = _PROMO_TERM_RE.search(desc)
    if not m:
        return None, None
    try:
        return int(m.group(1)), int(m.group(2))
    except Exception:
        return None, None


def _promo_series_key(desc: str) -> str:
    d = (desc or "").lower()
    d = _PROMO_TERM_RE.sub(" ", d)
    d = re.sub(r"[^a-z0-9]+", " ", d)
    d = " ".join(d.split()).strip()
    return d[:160] if d else "unknown_promo"


def _nearest_series_items_by_period(
    rows: List[Tuple[str, Optional[int], Optional[int], Decimal, Dict[str, Any]]],
    target_period_end: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    before: Optional[Dict[str, Any]] = None
    after: Optional[Dict[str, Any]] = None
    for pe, _cur, _tot, _amt, it in rows:
        if not pe:
            continue
        if pe < target_period_end:
            before = it
            continue
        if pe > target_period_end and after is None:
            after = it
            break
    return before, after


@dataclass(frozen=True)
class CaseFileInput:
    name: str
    kind: str  # "pdf" | "image" | "csv" | "unknown"
    content_bytes: bytes


# -----------------------------
# Core Case Processor
# -----------------------------
def analyze_case_files(
    *,
    files: List[CaseFileInput],
    min_text_chars: int = 400,
    ocr_enabled: bool = False,
    tesseract_cmd: Optional[str] = None,
    user_question: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Deterministic, fail-closed case analyzer focused on Verizon statements.

    Produces:
    - Deduped statements
    - Per-line timeline (by line_id ending digits)
    - Findings for: reconnect fees, late fees, promo changes, billed-after-disconnect contradictions
    - Evidence pointers come from verizon_structurer outputs

    IMPORTANT:
    - verizon_structurer.py is the single source of truth for per-statement summary rollups.
    - This file consumes st["summary"] and does NOT recompute fee/credit rollups.
    """
    # Build structured statements (PDF only for now; images/csv handled later)
    structured: List[Dict[str, Any]] = []
    unsupported: List[Dict[str, Any]] = []
    file_hashes: List[str] = []

    for f in files:
        fh = sha256_bytes(f.content_bytes)
        file_hashes.append(fh)

        if f.kind != "pdf":
            unsupported.append(
                {
                    "file": {"name": f.name, "hash": fh, "type": f.kind},
                    "status": "UNSUPPORTED",
                    "reason": "Only PDF statements are structured in this stage. (Images/CSVs can be added next.)",
                }
            )
            continue

        st = structure_verizon_pdf_bytes(
            file_name=f.name,
            pdf_bytes=f.content_bytes,
            min_text_chars=min_text_chars,
            ocr_enabled=ocr_enabled,
            tesseract_cmd=tesseract_cmd,
        )
        structured.append(st)

    case_id = _stable_case_id(file_hashes)

    # Dedupe statements deterministically
    deduped: Dict[str, Dict[str, Any]] = {}
    duplicates: List[Dict[str, Any]] = []

    for st in structured:
        header = st.get("header") or {}
        file_info = (st.get("file") or {})
        file_hash = str(file_info.get("hash") or "")
        key = _statement_key(header, file_hash=file_hash)

        if key in deduped:
            duplicates.append(
                {
                    "status": "DUPLICATE",
                    "dedupe_key": key,
                    "file": file_info,
                    "header": header,
                }
            )
        else:
            deduped[key] = st

    statements = list(deduped.values())

    # Sort statements by billing period end date (then by file hash)
    def _stmt_sort(st: Dict[str, Any]) -> Tuple[str, str]:
        h = st.get("header") or {}
        bp = h.get("billing_period") or {}
        end = _parse_iso_date(bp.get("end"))
        end_key = end.isoformat() if end else "0000-00-00T00:00:00"
        file_hash = str((st.get("file") or {}).get("hash") or "")
        return (end_key, file_hash)

    statements.sort(key=_stmt_sort)

    # Build per-statement per-line summaries
    per_statement_lines: List[Dict[str, Any]] = []
    line_timeline: Dict[str, List[Dict[str, Any]]] = {}

    # Case-level aggregation of per-statement summaries (deterministic; sums strings)
    case_summary_totals = {
        "reconnect_fee_total": "0.00",
        "other_fee_total": "0.00",
        "fees_non_tax_total": "0.00",
        "credits_total": "0.00",
    }

    for st in statements:
        h = st.get("header") or {}
        f = st.get("file") or {}
        ledger = st.get("ledger") or []
        events = st.get("events") or []
        st_summary = st.get("summary") or {}
        st_summary_totals = (st_summary.get("totals") or {}) if isinstance(st_summary, dict) else {}

        # Aggregate case summary totals from statement summary totals
        for k in list(case_summary_totals.keys()):
            if k in st_summary_totals:
                case_summary_totals[k] = _safe_sum_money_str(
                    case_summary_totals[k], str(st_summary_totals.get(k) or "0.00")
                )

        bp = h.get("billing_period") or {}
        period_end = bp.get("end")

        # Summary-by-line source of truth from verizon_structurer
        summary_by_line_list = st_summary.get("by_line") if isinstance(st_summary, dict) else None
        if not isinstance(summary_by_line_list, list):
            summary_by_line_list = []

        summary_by_line: Dict[str, Dict[str, Any]] = {}
        for rec in summary_by_line_list:
            if not isinstance(rec, dict):
                continue
            lid = _normalize_summary_line_id(rec.get("line_id"))
            summary_by_line[lid] = {
                "line_id": rec.get("line_id"),
                "reconnect_fee_total": str(rec.get("reconnect_fee_total") or "0.00"),
                "other_fee_total": str(rec.get("other_fee_total") or "0.00"),
                "fees_non_tax_total": str(rec.get("fees_non_tax_total") or "0.00"),
                "credits_total": str(rec.get("credits_total") or "0.00"),
            }

        # Gather by line_id (case_processor enriches with raw charges/events/flags only)
        by_line: Dict[str, Dict[str, Any]] = {}

        def _ensure_line(line_id: str) -> Dict[str, Any]:
            if line_id not in by_line:
                roll = summary_by_line.get(line_id) or _zero_summary_rollup(line_id)
                by_line[line_id] = {
                    "line_id": line_id,
                    "charges": [],  # ledger items (raw)
                    "events": [],  # event items (raw)
                    "summary": roll,  # SOURCE OF TRUTH: per-line rollups from verizon_structurer
                    "flags": {
                        "has_disconnect_event": False,
                        "has_reconnect_event": False,
                        "has_plan_changed_event": False,
                        "has_any_positive_charge": False,
                    },
                }
            return by_line[line_id]

        # ledger (for evidence + findings + timeline)
        for it in ledger:
            if _should_ignore_ledger_item(it):
                continue

            line_id = it.get("line_id") or "UNKNOWN"
            line_id = str(line_id)
            rec = _ensure_line(line_id)
            rec["charges"].append(it)

            amt = _safe_decimal(it.get("amount"))
            if amt is not None and amt > 0:
                rec["flags"]["has_any_positive_charge"] = True

        # events (kept under UNKNOWN; no inference)
        for ev in events:
            ev_type = str(ev.get("type") or "")
            rec = _ensure_line("UNKNOWN")
            rec["events"].append(ev)

            if ev_type == "service_disconnected":
                rec["flags"]["has_disconnect_event"] = True
            if ev_type == "service_reconnected":
                rec["flags"]["has_reconnect_event"] = True
            if ev_type == "plan_changed":
                rec["flags"]["has_plan_changed_event"] = True

        # Ensure "account" summary line is represented if present (even if ledger had no line_id=None items)
        if "account" in summary_by_line and "account" not in by_line:
            _ensure_line("account")

        # Freeze per-statement summary
        stmt_lines = sorted(by_line.values(), key=lambda x: str(x.get("line_id") or ""))
        per_statement_lines.append(
            {
                "file": f,
                "header": h,
                "period_end": period_end,
                "summary_totals": {
                    "reconnect_fee_total": str(st_summary_totals.get("reconnect_fee_total") or "0.00"),
                    "other_fee_total": str(st_summary_totals.get("other_fee_total") or "0.00"),
                    "fees_non_tax_total": str(st_summary_totals.get("fees_non_tax_total") or "0.00"),
                    "credits_total": str(st_summary_totals.get("credits_total") or "0.00"),
                },
                "lines": stmt_lines,
            }
        )

        # Add to timeline
        for rec in stmt_lines:
            lid = str(rec.get("line_id") or "UNKNOWN")
            if lid not in line_timeline:
                line_timeline[lid] = []
            line_timeline[lid].append(
                {
                    "period_end": period_end,
                    "file": f,
                    "header": h,
                    "summary": rec.get("summary") or _zero_summary_rollup(lid),
                    "flags": rec.get("flags") or {},
                    "charges": rec.get("charges") or [],
                    "events": rec.get("events") or [],
                }
            )

    # -----------------------------
    # Findings (deterministic)
    # -----------------------------
    findings: List[Dict[str, Any]] = []

    # 1) Reconnect fees (ledger category) — evidence-backed line items
    reconnect_items: List[Dict[str, Any]] = []
    for st in statements:
        for it in (st.get("ledger") or []):
            if _should_ignore_ledger_item(it):
                continue
            if str(it.get("category") or "") == "reconnect_fee":
                reconnect_items.append(it)

    reconnect_total = Decimal("0.00")
    for it in reconnect_items:
        amt = _safe_decimal(it.get("amount"))
        if amt is not None:
            reconnect_total += amt

    if reconnect_items:
        fid = "f_reconnect_" + sha256_text("reconnect|" + str(reconnect_total))[:16]
        findings.append(
            {
                "id": fid,
                "type": "reconnect_fees",
                "summary": f"Reconnect fees found: total {str(reconnect_total.quantize(Decimal('0.01')))} across all statements.",
                "total": str(reconnect_total.quantize(Decimal("0.01"))),
                "items": reconnect_items,  # includes evidence per item
                "why": "Document shows these line-items but does not state why unless an explicit reason appears in the statement text.",
            }
        )

    # 2) Late fees (ledger category)
    late_items: List[Dict[str, Any]] = []
    for st in statements:
        for it in (st.get("ledger") or []):
            if _should_ignore_ledger_item(it):
                continue
            if str(it.get("category") or "") == "late_fee":
                late_items.append(it)

    late_total = Decimal("0.00")
    for it in late_items:
        amt = _safe_decimal(it.get("amount"))
        if amt is not None:
            late_total += amt

    if late_items:
        fid = "f_late_" + sha256_text("late|" + str(late_total))[:16]
        findings.append(
            {
                "id": fid,
                "type": "late_fees",
                "summary": f"Late fees found: total {str(late_total.quantize(Decimal('0.01')))} across all statements.",
                "total": str(late_total.quantize(Decimal("0.01"))),
                "items": late_items,
                "why": "Document shows these line-items but does not state why unless an explicit reason appears in the statement text.",
            }
        )

    # 3) Promo credit continuity / amount changes / term gaps per line_id (deterministic, no expected totals)
    for lid, entries in line_timeline.items():
        if lid == "UNKNOWN":
            continue

        # timeline periods for this line (used for "missing in period" checks)
        timeline_periods = sorted(
            {str(e.get("period_end") or "") for e in (entries or []) if str(e.get("period_end") or "")}
        )

        # group promo credits into series (per line) using normalized description key
        series: Dict[str, List[Tuple[str, Optional[int], Optional[int], Decimal, Dict[str, Any]]]] = {}

        for e in entries:
            period_end = str(e.get("period_end") or "")
            for it in (e.get("charges") or []):
                if _should_ignore_ledger_item(it):
                    continue
                if str(it.get("category") or "") != "promo_credit":
                    continue
                amt = _safe_decimal(it.get("amount"))
                if amt is None:
                    continue

                desc = str(it.get("description") or "")
                skey = _promo_series_key(desc)
                cur_n, tot_n = _promo_term_numbers(it)

                series.setdefault(skey, []).append((period_end, cur_n, tot_n, amt, it))

        # per-series checks
        for skey, rows in series.items():
            rows.sort(key=lambda x: x[0])

            # 3a) Amount changes within the same promo series
            last_amt: Optional[Decimal] = None
            last_period: Optional[str] = None
            for period_end, _cur_n, _tot_n, amt, it in rows:
                if not period_end:
                    continue
                if last_amt is None:
                    last_amt = amt
                    last_period = period_end
                    continue
                if amt != last_amt:
                    fid = "f_promo_change_" + sha256_text(f"{lid}|{skey}|{last_period}->{period_end}|{last_amt}->{amt}")[:16]
                    findings.append(
                        {
                            "id": fid,
                            "type": "promo_amount_changed",
                            "line_id": lid,
                            "promo_series": skey,
                            "summary": (
                                f"Promo credit amount changed for line ending {lid}: "
                                f"{str(last_amt)} (period end {last_period}) → {str(amt)} (period end {period_end})."
                            ),
                            "evidence": [it.get("evidence")] if it.get("evidence") else [],
                            "note": "Document shows a change. Expected amount is not assumed unless explicitly stated in documents.",
                        }
                    )
                    last_amt = amt
                    last_period = period_end

            # 3b) Term-number gaps (e.g., Credit 22 of 36 → Credit 24 of 36)
            prev_cur: Optional[int] = None
            prev_pe: Optional[str] = None
            prev_it: Optional[Dict[str, Any]] = None

            for period_end, cur_n, _tot_n, _amt, it in rows:
                if cur_n is None or not period_end:
                    continue
                if prev_cur is None:
                    prev_cur = cur_n
                    prev_pe = period_end
                    prev_it = it
                    continue

                if cur_n > (prev_cur + 1):
                    missing_terms = list(range(prev_cur + 1, cur_n))
                    before_ev = (prev_it or {}).get("evidence") if prev_it else None
                    after_ev = it.get("evidence")

                    fid = "f_promo_term_gap_" + sha256_text(
                        f"{lid}|{skey}|{prev_pe}->{period_end}|{prev_cur}->{cur_n}|{','.join(map(str, missing_terms))}"
                    )[:16]
                    findings.append(
                        {
                            "id": fid,
                            "type": "promo_term_gap",
                            "line_id": lid,
                            "promo_series": skey,
                            "summary": (
                                f"Promo credit term gap for line ending {lid}: "
                                f"term {prev_cur} (period end {prev_pe}) → term {cur_n} (period end {period_end}). "
                                f"Missing term numbers: {', '.join(str(n) for n in missing_terms)}."
                            ),
                            "missing_terms": missing_terms,
                            "evidence": [ev for ev in [before_ev, after_ev] if ev],
                            "note": "This flags gaps in stated term numbering only. No expected dollar totals are assumed.",
                        }
                    )

                prev_cur = cur_n
                prev_pe = period_end
                prev_it = it

            # 3c) Missing promo in an intermediate statement period (appearance gap)
            series_periods = sorted({pe for pe, _c, _t, _a, _it in rows if pe})
            if timeline_periods and len(series_periods) >= 2:
                start_pe = series_periods[0]
                end_pe = series_periods[-1]
                series_period_set = set(series_periods)

                for pe in timeline_periods:
                    if pe <= start_pe or pe >= end_pe:
                        continue
                    if pe in series_period_set:
                        continue

                    before_it, after_it = _nearest_series_items_by_period(rows, pe)
                    before_ev = (before_it or {}).get("evidence") if before_it else None
                    after_ev = (after_it or {}).get("evidence") if after_it else None

                    fid = "f_promo_missing_period_" + sha256_text(f"{lid}|{skey}|missing|{pe}")[:16]
                    findings.append(
                        {
                            "id": fid,
                            "type": "promo_missing_in_period",
                            "line_id": lid,
                            "promo_series": skey,
                            "period_end": pe,
                            "summary": (
                                f"Promo credit series present before and after but not found in statement period end {pe} "
                                f"for line ending {lid}."
                            ),
                            "evidence": [ev for ev in [before_ev, after_ev] if ev],
                            "note": "This flags a missing promo line-item in that statement period. No expected dollar totals are assumed.",
                        }
                    )

    # 4) Contradiction: disconnected event then later positive charges
    for lid, entries in line_timeline.items():
        if lid == "UNKNOWN":
            continue

        disconnect_periods = []
        for e in entries:
            if e.get("flags", {}).get("has_disconnect_event") is True:
                disconnect_periods.append(str(e.get("period_end") or ""))

        if not disconnect_periods:
            continue

        first_disc = sorted(disconnect_periods)[0]

        # Any later statement with positive charge totals?
        for e in entries:
            pe = str(e.get("period_end") or "")
            if pe and first_disc and pe > first_disc:
                if e.get("flags", {}).get("has_any_positive_charge") is True:
                    fid = "f_disc_billed_" + sha256_text(f"{lid}|{first_disc}|{pe}")[:16]
                    findings.append(
                        {
                            "id": fid,
                            "type": "billed_after_disconnect",
                            "line_id": lid,
                            "summary": (
                                f"Possible contradiction for line ending {lid}: statement shows disconnection "
                                f"(period end {first_disc}) but later statements show positive charges (period end {pe})."
                            ),
                            "note": "Document shows both signals. Document does not state why.",
                        }
                    )
                    break

    # Deterministic sorting
    findings.sort(key=_findings_sort_key)

    # Follow-up (ONE specific ask only if blocking)
    followup = {"needed": False}
    if not statements and unsupported:
        followup = {
            "needed": True,
            "request": "Upload at least one Verizon bill PDF (not a screenshot image) OR enable OCR for image-only PDFs so text can be extracted deterministically.",
            "why_it_matters": "Without readable statement text, the system cannot produce evidence-backed, dispute-ready findings.",
        }

    return {
        "status": "OK",
        "case_id": case_id,
        "question": (user_question or "").strip()[:500] if user_question else None,
        "dedupe": {
            "statements_received": len(structured),
            "statements_deduped": len(statements),
            "duplicates": duplicates,
        },
        "unsupported": unsupported,
        "case_summary": {"totals": case_summary_totals},
        "statements": per_statement_lines,  # lines now consume structurer rollups (single source of truth)
        "findings": findings,
        "followup": followup,
    }
