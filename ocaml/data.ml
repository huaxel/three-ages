open Core
open Yojson.Safe.Util
open Model

let string_field name json = json |> member name |> to_string
let string_or_int = function
  | `Int value -> Int.to_string value
  | value -> to_string value

let optional_string name json = json |> member name |> to_option to_string

let status = function
  | "pending" -> Claim_status.Pending
  | "proxy" -> Claim_status.Proxy
  | "source description" -> Claim_status.Source_description
  | "documented proxy" -> Claim_status.Documented_proxy
  | "reviewed" -> Claim_status.Reviewed
  | value -> failwith ("unknown claim status: " ^ value)

let evidence json =
  { Evidence.asset_id = string_field "asset_id" json
  ; epoch =
      (match json |> member "epoch" with
       | `Int year -> Int.to_string year
       | value -> to_string value)
  ; description = string_field "observation" json
  ; source_url = string_field "source_url" json
  ; preview = string_field "preview" json
  ; licence = string_field "licence" json
  ; credit = string_field "credit" json }

let structural_by_source =
  lazy
    (let document = Yojson.Safe.from_string Structural_data.three_ages_structural_crops_dot_json in
     document |> member "records" |> to_list
     |> List.map ~f:(fun record ->
          string_field "source_id" record,
          (record |> member "assets" |> to_list |> List.map ~f:(fun asset ->
             { Structural.epoch = asset |> member "epoch" |> string_or_int
             ; preview = string_field "crop_preview" asset })))
     |> String.Map.of_alist_exn)

let structural_for source_id =
  Map.find (Lazy.force structural_by_source) source_id |> Option.value ~default:[]

let buildings_by_id =
  lazy
    (let document = Yojson.Safe.from_string Buildings_data.grand_place_buildings_dot_json in
     document |> member "records" |> to_list
     |> List.map ~f:(fun record -> string_field "id" record, record)
     |> String.Map.of_alist_exn)

let case json =
  let register = json |> member "register" in
  let source_id = string_field "source_id" json in
  let building = Map.find_exn (Lazy.force buildings_by_id) source_id in
  { Case.id = source_id
  ; name = string_field "name" building
  ; address = string_field "address" building
  ; register_value =
      (match register |> member "value" with
       | `Int year -> Int.to_string year
       | value -> to_string value)
  ; register_status = status (string_field "status" register)
  ; register_note = string_field "note" register
  ; facade = string_field "value" (json |> member "facade")
  ; facade_status = status (string_field "status" (json |> member "facade"))
  ; structure = string_field "value" (json |> member "structure")
  ; structure_status = status (string_field "status" (json |> member "structure"))
  ; evidence = json |> member "image_evidence" |> to_list |> List.map ~f:evidence
  ; structural = structural_for source_id }

let cases () =
  let document = Yojson.Safe.from_string Pilot_data.three_ages_pilot_dot_json in
  document |> member "records" |> to_list |> List.map ~f:case
