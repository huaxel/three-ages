open Core
open Bonsai_web_test
open Yojson.Safe.Util

module Node_helpers = Virtual_dom_test_helpers.Node_helpers

let tree handle =
  Handle.result handle |> Node_helpers.unsafe_convert_exn

let textarea_value handle =
  match Node_helpers.select_first_exn (tree handle) ~selector:"#draft-observation" with
  | Node_helpers.Element { string_properties; _ } ->
    List.Assoc.find string_properties "value" ~equal:String.equal |> Option.value ~default:""
  | _ -> failwith "draft observation is not an element"

let download_attributes handle =
  Node_helpers.select (tree handle) ~selector:"a"
  |> List.find_map ~f:(function
       | Node_helpers.Element { attributes; _ }
         when List.Assoc.mem attributes "download" ~equal:String.equal -> Some attributes
       | _ -> None)

let required_attribute attributes name =
  List.Assoc.find attributes name ~equal:String.equal
  |> Option.value_exn ~message:("missing download attribute: " ^ name)

let stabilize handle = Handle.recompute_view_until_stable handle

let () =
  List.iter
    [ "javascript:alert(1)"; "data:text/html,test"; "http://example.test"; "https:relative" ]
    ~f:(fun unsafe ->
      if not (String.equal (App.safe_external_url unsafe) "#")
      then failwith ("unsafe external URL was accepted: " ^ unsafe));
  let safe_url = "https://example.test/source" in
  if not (String.equal (App.safe_external_url safe_url) safe_url)
  then failwith "safe HTTPS URL was rejected";
  List.iter
    [ "../README.md"
    ; "data/."
    ; "data/.."
    ; "data/historical/.."
    ; "data/../../README.md"
    ; "/etc/passwd"
    ; "data:image/svg+xml,test"
    ; "data/%2e%2e/README.md"
    ]
    ~f:(fun unsafe ->
      if Option.is_some (App.safe_asset_path unsafe)
      then failwith ("unsafe asset path was accepted: " ^ unsafe));
  List.iter
    [ "data/source.png"; "data/historical/source.jpg"; "data/structural/crop.png" ]
    ~f:(fun expected ->
      match App.safe_asset_path expected with
      | Some actual when String.equal actual expected -> ()
      | _ -> failwith ("safe asset path was rejected: " ^ expected));
  let register_review =
    { Reviews.Review.source_id = "009"
    ; evidence_id = "register-009"
    ; kind = Register
    ; observation = "The date is a reconstruction proxy."
    ; decision = "retain as reconstruction evidence"
    ; reviewer = "Test reviewer"
    ; reviewed_at = "2026-09-20"
    ; confidence = "medium"
    }
  in
  let rendered_review = App.review_text register_review in
  List.iter
    [ "register-009"
    ; "retain as reconstruction evidence"
    ; "The date is a reconstruction proxy."
    ; "medium confidence"
    ; "Test reviewer"
    ; "2026-09-20"
    ]
    ~f:(fun expected ->
      if not (String.is_substring rendered_review ~substring:expected)
      then failwith ("review display omitted provenance: " ^ expected));
  let unknown_status_rejected =
    try
      ignore (Data.status "unexpected status");
      false
    with
    | Failure _ -> true
  in
  if not unknown_status_rejected then failwith "unknown claim status was silently accepted";
  let handle = Handle.create (Result_spec.vdom Fn.id) (App.component ()) in
  stabilize handle;
  let initial_text = Node_helpers.inner_text (tree handle) in
  List.iter
    [ "The Horn"
    ; "source description"
    ; "documented proxy"
    ; "1930–1935"
    ; "1996"
    ; "2022"
    ]
    ~f:(fun expected ->
      if not (String.is_substring initial_text ~substring:expected)
      then failwith ("rendered app is missing canonical value: " ^ expected));
  Handle.input_text handle ~get_vdom:Fn.id ~selector:"#draft-observation" ~text:"Case 005 draft";
  stabilize handle;
  if not (String.equal (textarea_value handle) "Case 005 draft")
  then failwith "draft input was not retained";

  Handle.click_on handle ~get_vdom:Fn.id ~selector:"#case-005";
  stabilize handle;
  if not (String.equal (textarea_value handle) "Case 005 draft")
  then failwith "re-clicking the active case deleted its draft";

  Handle.click_on handle ~get_vdom:Fn.id ~selector:"#case-009";
  stabilize handle;
  if not (String.is_empty (textarea_value handle))
  then failwith "case 005 draft leaked into case 009";

  Handle.input_text handle ~get_vdom:Fn.id ~selector:"#draft-observation" ~text:"Case 009 draft";
  Handle.click_on handle ~get_vdom:Fn.id ~selector:"#confidence-medium";
  stabilize handle;
  let attributes =
    download_attributes handle |> Option.value_exn ~message:"complete draft did not expose a download"
  in
  let name = required_attribute attributes "download" in
  if not (String.equal name "three-ages-review-009-B031587.json")
  then failwith ("draft download was attributed to " ^ name);
  let href = required_attribute attributes "href" in
  let prefix = "data:application/json;charset=utf-8," in
  let payload = String.chop_prefix_exn href ~prefix |> Uri.pct_decode |> Yojson.Safe.from_string in
  let require_json_field field expected =
    let actual = payload |> member field |> to_string in
    if not (String.equal actual expected)
    then failwith (sprintf "download %s was %S, expected %S" field actual expected)
  in
  require_json_field "source_id" "009";
  require_json_field "asset_id" "B031587";
  require_json_field "observation" "Case 009 draft";
  require_json_field "confidence" "medium";

  Handle.click_on handle ~get_vdom:Fn.id ~selector:"#case-005";
  stabilize handle;
  if not (String.is_empty (textarea_value handle))
  then failwith "case 009 draft leaked back into case 005";

  Handle.click_on handle ~get_vdom:Fn.id ~selector:"#case-024";
  stabilize handle;
  Handle.input_text handle ~get_vdom:Fn.id ~selector:"#draft-observation" ~text:"First asset draft";
  Handle.click_on handle ~get_vdom:Fn.id ~selector:"#draft-asset-commons-balance-2011-01";
  stabilize handle;
  if not (String.is_empty (textarea_value handle))
  then failwith "draft leaked between two assets on the same case";
  Handle.input_text handle ~get_vdom:Fn.id ~selector:"#draft-observation" ~text:"Commons asset draft";
  Handle.click_on handle ~get_vdom:Fn.id ~selector:"#draft-asset-commons-balance-2011-01";
  stabilize handle;
  if not (String.equal (textarea_value handle) "Commons asset draft")
  then failwith "re-clicking the selected asset deleted its draft";
  Handle.click_on handle ~get_vdom:Fn.id ~selector:"#confidence-high";
  stabilize handle;
  let attributes =
    download_attributes handle |> Option.value_exn ~message:"asset-specific draft did not expose a download"
  in
  let name = required_attribute attributes "download" in
  if not (String.equal name "three-ages-review-024-commons-balance-2011-01.json")
  then failwith ("multi-asset draft download was attributed to " ^ name);
  let payload =
    required_attribute attributes "href"
    |> String.chop_prefix_exn ~prefix
    |> Uri.pct_decode
    |> Yojson.Safe.from_string
  in
  if not (String.equal (payload |> member "asset_id" |> to_string) "commons-balance-2011-01")
  then failwith "multi-asset draft JSON has the wrong evidence id";
  print_endline "Bonsai case-and-asset interaction test passed"
