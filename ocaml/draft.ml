open Core
open Model

module Draft = struct
  type t = {
    source_id : string;
    asset_id : string;
    observation : string;
    confidence : Draft_confidence.t;
  }
  [@@deriving sexp, equal]

  let empty ~source_id ~asset_id =
    { source_id; asset_id; observation = ""; confidence = Draft_confidence.Unassigned }

  let for_source draft ~source_id ~asset_id =
    if String.equal draft.source_id source_id then draft else empty ~source_id ~asset_id

  let is_complete draft =
    not (String.is_empty draft.asset_id)
    && not (String.is_empty (String.strip draft.observation))
    && not (Draft_confidence.equal draft.confidence Draft_confidence.Unassigned)

  let to_json draft =
    `Assoc
      [ "source_id", `String draft.source_id
      ; "asset_id", `String draft.asset_id
      ; "observation", `String draft.observation
      ; "confidence", `String (Draft_confidence.label draft.confidence)
      ]
end
