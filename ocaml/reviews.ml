open Core
open Yojson.Safe.Util

module Review = struct
  type kind = Facade | Structural | Register

  type t = {
    source_id : string;
    evidence_id : string;
    kind : kind;
    observation : string;
    decision : string;
    reviewer : string;
    reviewed_at : string;
    confidence : string;
  }
end

let string_or_empty name json =
  match json |> member name with
  | `Null -> ""
  | value -> to_string value

let record kind ~evidence_field ~observation item =
  { Review.source_id = string_or_empty "source_id" item
  ; evidence_id = string_or_empty evidence_field item
  ; kind
  ; observation
  ; decision = string_or_empty "register_decision" item
  ; reviewer = string_or_empty "reviewer" item
  ; reviewed_at = string_or_empty "reviewed_at" item
  ; confidence = string_or_empty "confidence" item }

let image_records json =
  json |> member "records" |> to_list |> List.concat_map ~f:(fun item ->
    [ Review.Facade, string_or_empty "facade_observation" item
    ; Review.Structural, string_or_empty "structural_observation" item
    ]
    |> List.filter_map ~f:(fun (kind, observation) ->
         if String.is_empty (String.strip observation)
         then None
         else Some (record kind ~evidence_field:"asset_id" ~observation item)))

let records kind ~evidence_field ~observation_field json =
  json |> member "records" |> to_list |> List.map ~f:(fun item ->
    record kind ~evidence_field ~observation:(string_or_empty observation_field item) item)

let all_reviews =
  lazy
    (let parse text = Yojson.Safe.from_string text in
     image_records (parse Image_reviews_data.three_ages_image_reviews_dot_json)
     @ records Review.Structural ~evidence_field:"comparison_id"
         ~observation_field:"structural_observation"
         (parse Structural_reviews_data.three_ages_structural_reviews_dot_json)
     @ records Review.Register ~evidence_field:"claim_id"
         ~observation_field:"register_observation"
         (parse Register_reviews_data.three_ages_register_reviews_dot_json))

let all () = Lazy.force all_reviews

let for_case source_id =
  all () |> List.filter ~f:(fun review -> String.equal review.Review.source_id source_id)
