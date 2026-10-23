# Three Ages — Dataset Evaluation, Provenance and Audit

This document defines the methodology for evaluating the Three Ages prototype facade dataset, specifies group leakage and split feasibility rules, provides cryptographic frozen-hash recommendations, and articulates the limitations of human historian reviews.

## Standalone Evaluation and Audit Script

The dataset audit script is located at [`prototypes/audit_facade_dataset.py`](../prototypes/audit_facade_dataset.py). It operates as a standalone Python utility (standard library only) that evaluates review worksheets without requiring a machine learning framework.

Run the audit from the repository root:

```bash
python3 prototypes/audit_facade_dataset.py
```

Optional flags:
- `--json`: Output full audit metrics as machine-readable JSON.
- `--csv <path>`: Audit an alternative worksheet or session CSV.
- `--test-ratio <float>`: Test split ratio for deterministic group allocation (default: `0.2`).
- `--seed <int>`: Deterministic seed for group hash assignment (default: `42`).
- `--check-readiness`: Exit with code 1 if dataset is not ready for held-out evaluation.

Comprehensive unit and integration tests run via:

```bash
python3 prototypes/test_audit_facade_dataset.py
```

---

## Weak Labels vs. Ground Truth

A critical methodological boundary of the Three Ages project is the strict isolation between source-described style text and human reviewer visual classification:

1. **`source_style_text` / `source_style_label` is WEAK METADATA**:
   - Extracted from municipal inventory descriptions or museum catalogue notes.
   - Represents descriptive, 19th/20th-century inventories rather than standardized taxonomies.
   - Frequently describes gables, statues, or ornamental programs rather than period styles.
   - **Must NEVER be used as ground truth or as a benchmark evaluation target.**
2. **`facade_style` is REVIEWER GROUND TRUTH**:
   - Assigned by human reviewers from visual inspection of historical images.
   - Constrained to the controlled vocabulary (`baroque`, `classical french`, `renaissance-inspired`, `mixed`, `other`, `uncertain`, `not assessable`).
   - Requires explicit reviewer identification, ISO 8601 timestamp, observation notes, and confidence rating (`low`, `medium`, `high`).
   - Currently, 0 of 77 images carry completed reviewer style labels in this manifest; the committed dataset is entirely in a **pending review** state. (Seventeen curated pilot image reviews live in `three-ages-image-review.csv`; this manifest carries source-described weak labels only.)

---

## Dataset Provenance and Frozen-Hash Recommendation

To ensure auditable, reproducible evaluations and prevent data drift during review iterations:

1. **Cryptographic Checksum Pinning**:
   - Each review worksheet must be accompanied by its SHA-256 digest (e.g. `three-ages-image-review.csv` SHA-256 is tracked and verified by `audit_facade_dataset.py`).
   - Every historical image asset is pinned to its SHA-256 digest in `preview_sha256` and verified during snapshot validation.
   - Any modification to preview pixels or metadata forces an explicit review refactor rather than silent mutation.
2. **Frozen Dataset Releases**:
   - Prior to training or benchmark evaluation, an immutable snapshot release must be tagged with a frozen git commit and cryptographic manifest.
   - The manifest records:
     - Exact worksheet SHA-256;
     - Image count, facade unit count, and building record count;
     - Full provenance chains: source URLs, IIIF endpoints, credit lines, and open-data licence statements;
     - The exact output of `python3 prototypes/audit_facade_dataset.py --json`.

---

## Group Leakage Invariants

Standard random train/test or cross-validation splitting induces severe optimistic bias on architectural datasets. The audit script enforces strict group-level isolation:

1. **Facade Unit Grouping (`facade_unit_id`)**:
   - The 34 Grand Place building records map to 27 architecturally distinct facade units.
   - Multi-building compositions (such as Grand-Place 13–19, *Maison des Ducs de Brabant*, spanning 7 records) form a single architectural unit (`gp-13-19-ducs-de-brabant`).
   - Multi-image units (e.g. Grand-Place 6 or 9, which contain both 1942 BALaT details and 1969 full-facade views) must never have their images split across training and test partitions. If a model sees one image of *The Swan* during training, evaluating it on another image of *The Swan* tests building instance re-identification, not generalizable style recognition.
2. **Image Checksum and Asset Grouping**:
   - If an identical image checksum (`preview_sha256`) or asset identifier appears in more than one record, all associated rows are grouped into the same connected component.
   - The audit verifies that:
     $$\text{Train}_{\text{units}} \cap \text{Test}_{\text{units}} = \emptyset$$
     $$\text{Train}_{\text{buildings}} \cap \text{Test}_{\text{buildings}} = \emptyset$$
     $$\text{Train}_{\text{hashes}} \cap \text{Test}_{\text{hashes}} = \emptyset$$

---

## Feasibility Criteria for Held-Out Evaluation

A meaningful held-out recognition score requires that:
1. **Labels are Reviewed**: Non-pending, complete reviewer annotations must exist.
2. **Minimum Class Unit Representation**: Every evaluated target style must appear in **at least two independent facade units** ($\ge 2$). In a leak-free group split, a singleton class can only appear in train or test, never both. Zero test instances make recall and precision undefined; zero train instances make learning impossible.
3. **Statistical Sample Size**: Total reviewed facade units must be sufficient ($\ge 4$ minimum, ideally $\ge 10$ per class) to provide meaningful confidence intervals.

**Current Dataset State**:
- Total records: 34
- Facade units: 27
- Historical images: 77
- Reviewed style labels: 0
- **Held-out recognition score feasibility: INFEASIBLE (insufficient data; all rows pending).**

---

## Historian Review Limitations

When interpreting reviewer annotations, the following architectural and historical limitations must be documented:

1. **Historicist Reconstructions and Composite Facades**:
   - Grand-Place facades are not monolithic single-period structures. Following the 1695 French bombardment, buildings were rebuilt in Baroque or Classical styles, and heavily restored or re-historicized in the late 19th century under City Architect Pierre-Victor Jamaer.
   - A facade may display a Renaissance ground floor, Baroque middle registers, and a 19th-century historicist gable. Forcing a discrete single-label classification involves qualitative trade-offs.
2. **Subjectivity and Inter-Annotator Variation**:
   - Style boundaries (e.g., distinguishing *Baroque* from *Classical French* or *Renaissance-inspired*) are qualitative and interpretive.
   - Reviewers record subjective certainty via `confidence` (`low`, `medium`, `high`) and qualitative evidence in `facade_observation`. Disagreements between reviewers represent real historical ambiguity rather than label noise.
3. **Geographic and Architectural Bias**:
   - The Grand Place is architecturally dominated by Baroque rebuildings. 15 of 27 units have Baroque source descriptions; Wikidata assigns Baroque architecture to 24 of the 33 house-category items (27 carry a style at all).
   - Widening the sample within the Grand Place cannot fix this class imbalance. Models evaluated on this square cannot generalize to Brussels architecture without sampling non-square buildings (e.g. Art Nouveau, Neoclassical, Gothic).
