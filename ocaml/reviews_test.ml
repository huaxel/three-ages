open Core

let review_record ?(facade = "") ?(structural = "") source_id =
  `Assoc
    [ "source_id", `String source_id
    ; "asset_id", `String ("asset-" ^ source_id)
    ; "facade_observation", `String facade
    ; "structural_observation", `String structural
    ; "reviewer", `String "Test reviewer"
    ; "reviewed_at", `String "2026-09-20"
    ; "confidence", `String "medium"
    ]

let () =
  let json =
    `Assoc
      [ "records",
        `List
          [ review_record ~structural:"Structural-only observation" "005"
          ; review_record ~facade:"Facade observation" ~structural:"Structural observation" "009"
          ]
      ]
  in
  let reviews = Reviews.image_records json in
  if List.length reviews <> 3 then failwith "image review observations were dropped";
  let observations = List.map reviews ~f:(fun review -> review.Reviews.Review.observation) in
  List.iter
    [ "Structural-only observation"; "Facade observation"; "Structural observation" ]
    ~f:(fun expected ->
      if not (List.mem observations expected ~equal:String.equal)
      then failwith ("missing observation: " ^ expected));
  let evidence_ids = List.map reviews ~f:(fun review -> review.Reviews.Review.evidence_id) in
  if not (List.mem evidence_ids "asset-005" ~equal:String.equal)
     || not (List.mem evidence_ids "asset-009" ~equal:String.equal)
  then failwith "image review evidence ids were dropped";
  let structural_count =
    List.count reviews ~f:(fun review ->
      match review.Reviews.Review.kind with
      | Reviews.Review.Structural -> true
      | Facade | Register -> false)
  in
  if structural_count <> 2 then failwith "structural image reviews were misclassified";
  let malformed =
    `Assoc
      [ "records",
        `List
          [ `Assoc
              [ "source_id", `Int 5
              ; "facade_observation", `String "Observation"
              ; "structural_observation", `String ""
              ]
          ]
      ]
  in
  let malformed_rejected =
    try
      ignore (Reviews.image_records malformed);
      false
    with
    | Yojson.Safe.Util.Type_error _ -> true
  in
  if not malformed_rejected then failwith "malformed review field type was silently accepted";
  print_endline "Review decoding test passed"
