open Core
open Model

let () =
  let incomplete =
    { Draft.Draft.source_id = "005"
    ; asset_id = "T084580"
    ; observation = ""
    ; confidence = Draft_confidence.Unassigned }
  in
  if Draft.Draft.is_complete incomplete then failwith "empty draft marked complete";
  let complete =
    { Draft.Draft.source_id = "005"
    ; asset_id = "T084580"
    ; observation = "Visible facade detail retained."
    ; confidence = Draft_confidence.Medium }
  in
  if not (Draft.Draft.is_complete complete) then failwith "complete draft rejected";
  let switched = Draft.Draft.for_source complete ~source_id:"009" ~asset_id:"B031587" in
  if not (String.equal switched.source_id "009")
     || not (String.equal switched.asset_id "B031587")
     || not (String.is_empty switched.observation)
     || not (Draft_confidence.equal switched.confidence Draft_confidence.Unassigned)
  then failwith "draft leaked across source ids";
  let json = Draft.Draft.to_json complete |> Yojson.Safe.to_string in
  if not (String.is_substring json ~substring:"medium") then failwith "confidence missing";
  if not (String.is_substring json ~substring:"T084580") then failwith "asset id missing";
  print_endline "Draft contract test passed"
