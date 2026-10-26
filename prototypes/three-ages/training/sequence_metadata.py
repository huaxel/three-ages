"""Explicit Mapillary acquisition evidence, never building-identity evidence.

No photographer, timestamp, location or filename heuristics are used here.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping


def main():
    """Inspect an existing CSV without decoding images or altering its rows."""
    import argparse
    import csv
    import hashlib
    import io
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description='Report explicit Mapillary sequence evidence; absence is UNKNOWN')
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or args.out.is_symlink():
        parser.error('output exists; refusing to replace any artifact')
    try:
        raw = args.manifest.read_bytes()
        reader = csv.DictReader(io.StringIO(raw.decode('utf-8'), newline=''), strict=True)
        fields = reader.fieldnames or []
        if (len(fields) != len(set(fields)) or
                not {'source_filename', 'building_id', 'split'} <= set(fields)):
            raise ValueError('canonical source ID/building/split columns required')
        rows = list(reader)
        if any(None in row or any(value is None for value in row.values()) or
               not row['building_id'].strip() or row['split'] not in ('train', 'val', 'test') for row in rows):
            raise ValueError('malformed sequence manifest row')
        report = {'schema': 'sequence-evidence-audit/1', 'manifest_rows': len(rows),
                  'sequence_column_present': 'sequence_id' in fields,
                  'input_sha256': hashlib.sha256(raw).hexdigest(),
                  'implementation_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  'evidence': sequence_groups(rows),
                  'isolation': 'not established; explicit acquisition metadata only',
                  'source_files_modified': False}
        payload = json.dumps(report, indent=2, allow_nan=False)+'\n'
        with args.out.open('x', encoding='utf-8') as handle:
            handle.write(payload)
    except (ValueError, OSError, csv.Error) as exc:
        parser.error(str(exc))
    evidence = report['evidence']
    print(f"{evidence['status']}: {evidence['known_rows']}/{evidence['row_count']} rows with explicit sequence IDs; no isolation proof")


def _identifier(value, field: str) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        raise ValueError(f"{field}: boolean is not an ID")
    if isinstance(value, int):
        if value < 0:
            raise ValueError(f"{field}: negative ID")
        return str(value)
    if isinstance(value, str):
        return value.strip()
    raise ValueError(f"{field}: expected string or integer ID")


def sequence_id(image: Mapping) -> str:
    """Return native sequence_id/sequence (string, integer, or {id: ...}).

    Missing, null and empty values mean unknown (''). Supplied nonempty IDs
    must agree. Integers normalize to decimal; floats and booleans are invalid.
    """
    if not isinstance(image, Mapping):
        raise ValueError("image metadata must be an object")
    values = []
    for field in ("sequence_id", "sequence"):
        value = image.get(field)
        if field == "sequence" and isinstance(value, Mapping):
            if "id" not in value:
                raise ValueError("sequence object must contain id")
            value = value["id"]
        normalized = _identifier(value, field)
        if normalized:
            values.append(normalized)
    if len(set(values)) > 1:
        raise ValueError("conflicting sequence_id and sequence IDs")
    return values[0] if values else ""


def sequence_groups(rows) -> dict:
    """Describe acquisition dependence using ONLY each row's sequence_id.

    Rows are mappings with source_filename (or source_id/image_id), building_id,
    split, and optional source (default 'mapillary'). Other sources are excluded.
    Source keys in the report are namespaced 'mapillary:<native ID>'. Repeated
    source IDs may have blank evidence but cannot have conflicting known IDs.
    Groups join validated sequence evidence across identical native source IDs;
    propagated memberships are counted separately, never written into input rows.
    Coverage counts only directly observed metadata, not propagated evidence.
    Status is UNKNOWN for zero coverage, PARTIAL otherwise, COMPLETE if all
    rows and unique sources have evidence. Empty cross-split groups prove no
    observed overlap only; never independence or common building identity.
    """
    total = known = excluded = 0
    sources = defaultdict(set)
    groups = {}
    observations = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("sequence diagnostic row must be an object")
        source = row.get("source", "mapillary")
        if not isinstance(source, str) or not source.strip():
            raise ValueError("source namespace must be a nonempty string")
        if source.lower().strip() != "mapillary":
            excluded += 1
            continue
        native = next((row.get(k) for k in ("source_filename", "source_id", "image_id")
                       if row.get(k) is not None and row.get(k) != ""), None)
        native = _identifier(native, "source ID")
        if not native:
            raise ValueError("Mapillary row requires explicit source ID")
        key = f"mapillary:{native}"
        seq = sequence_id({"sequence_id": row.get("sequence_id")})
        total += 1
        sources[key]  # count even unknown sources
        if seq:
            known += 1
            sources[key].add(seq)
            if len(sources[key]) > 1:
                raise ValueError(f"conflicting sequence IDs for {key}")
        values = []
        for field in ('building_id', 'split'):
            value = row.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'{field} must be a nonempty string')
            values.append(value.strip())
        if values[1] not in ('train', 'val', 'test'):
            raise ValueError('unknown split')
        observations.append((key, seq, *values))
    propagated = 0
    for key, observed_seq, bid, split in observations:
        if not sources[key]:
            continue
        seq = next(iter(sources[key]))
        propagated += int(not observed_seq)
        group_key = f"mapillary:{seq}"
        group = groups.setdefault(group_key, {"sequence_id": seq, "row_count": 0,
                                              "source_ids": set(), "building_ids": set(),
                                              "splits": set(), "propagated_rows": 0})
        group["row_count"] += 1
        group["source_ids"].add(key)
        group['propagated_rows'] += int(not observed_seq)
        group['building_ids'].add(bid)
        group['splits'].add(split)
    result_groups = []
    for key, group in sorted(groups.items()):
        result_groups.append({"key": key, **{k: sorted(v) if isinstance(v, set) else v
                                             for k, v in group.items()}})
    source_known = sum(bool(v) for v in sources.values())
    return {
        "namespace": "mapillary",
        "interpretation": "acquisition dependence; not building identity",
        "status": "UNKNOWN" if not known else "COMPLETE" if known == total else "PARTIAL",
        "row_count": total, "known_rows": known, "unknown_rows": total - known,
        "row_coverage": known / total if total else None,
        "unique_source_count": len(sources), "known_unique_sources": source_known,
        "unknown_unique_sources": len(sources) - source_known,
        "unique_source_coverage": source_known / len(sources) if sources else None,
        "excluded_rows": excluded,
        "propagated_rows": propagated,
        "groups": result_groups,
        "cross_split_groups": [g for g in result_groups if len(g["splits"]) > 1],
    }


if __name__ == '__main__':
    main()
