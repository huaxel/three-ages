open Core
open Model
open Bonsai_web
open Bonsai.Let_syntax

let text value = Vdom.Node.text value

let safe_external_url value =
  let url = Uri.of_string value in
  match Uri.scheme url, Uri.host url with
  | Some "https", Some _ -> value
  | _ -> "#"

let link ~url label =
  Vdom.Node.a
    ~attrs:[ Vdom.Attr.href (safe_external_url url)
           ; Vdom.Attr.target "_blank"
           ; Vdom.Attr.create "rel" "noopener noreferrer" ]
    [ text label ]

let claim_card ~label ~value ~status ~note =
  Vdom.Node.div
    ~attrs:[ Vdom.Attr.class_ "claim" ]
    [ Vdom.Node.h3 [ text label ]
    ; Vdom.Node.div ~attrs:[ Vdom.Attr.class_ "claim-value" ] [ text value ]
    ; Vdom.Node.span ~attrs:[ Vdom.Attr.class_ "status" ] [ text (Claim_status.label status) ]
    ; Vdom.Node.p [ text note ] ]

let review_label = function
  | Reviews.Review.Facade -> "Facade review"
  | Reviews.Review.Structural -> "Structural review"
  | Reviews.Review.Register -> "Register review"

let review_text review =
  let content =
    if String.is_empty review.Reviews.Review.decision
    then review.Reviews.Review.observation
    else if String.is_empty review.Reviews.Review.observation
    then review.Reviews.Review.decision
    else review.Reviews.Review.decision ^ ": " ^ review.Reviews.Review.observation
  in
  review_label review.Reviews.Review.kind ^ " [" ^ review.Reviews.Review.evidence_id ^ "]: "
  ^ content ^ " · " ^ review.Reviews.Review.confidence ^ " confidence"
  ^ " · reviewed by " ^ review.Reviews.Review.reviewer
  ^ " · " ^ review.Reviews.Review.reviewed_at

let review_view source_id =
  let reviews = Reviews.for_case source_id in
  let cards =
    List.map reviews ~f:(fun review ->
      Vdom.Node.li [ text (review_text review) ])
  in
  if List.is_empty cards
  then Vdom.Node.p ~attrs:[ Vdom.Attr.class_ "muted" ] [ text "No completed reviewer decisions." ]
  else Vdom.Node.ul cards

let safe_asset_path value =
  let safe_filename filename =
    not (String.is_empty filename)
    && not (String.equal filename ".")
    && not (String.equal filename "..")
    && String.for_all filename ~f:(fun character ->
         Char.is_alphanum character || Char.equal character '-' || Char.equal character '_'
         || Char.equal character '.')
  in
  match String.split value ~on:'/' with
  | [ "data"; filename ] when safe_filename filename -> Some value
  | [ "data"; ("historical" | "structural"); filename ] when safe_filename filename ->
    Some value
  | _ -> None

let preview_path value =
  safe_asset_path value
  |> Option.map ~f:(fun path -> "../prototypes/three-ages/" ^ path)
  |> Option.value ~default:""

let draft_review ~draft ~evidence_ids ~set_draft =
  let source_id = draft.Draft.Draft.source_id in
  let export_link =
    if Draft.Draft.is_complete draft
    then
      Vdom.Node.a
        ~attrs:[ Vdom.Attr.href
                   ("data:application/json;charset=utf-8,"
                    ^ Uri.pct_encode (Yojson.Safe.to_string (Draft.Draft.to_json draft)))
               ; Vdom.Attr.create "download"
                   ("three-ages-review-" ^ source_id ^ "-" ^ draft.asset_id ^ ".json") ]
        [ text "Download draft JSON" ]
    else Vdom.Node.none
  in
  let evidence_button asset_id =
    let selected = String.equal asset_id draft.asset_id in
    Vdom.Node.button
      ~attrs:[ Vdom.Attr.id ("draft-asset-" ^ asset_id)
             ; Vdom.Attr.class_ (if selected then "selected" else "")
             ; Vdom.Attr.create "aria-pressed" (Bool.to_string selected)
             ; Vdom.Attr.on_click (fun _ ->
                 if selected
                 then Effect.Ignore
                 else set_draft (Draft.Draft.empty ~source_id ~asset_id)) ]
      [ text asset_id ]
  in
  let confidence_button value =
    let label = Draft_confidence.label value in
    Vdom.Node.button
      ~attrs:[ Vdom.Attr.id ("confidence-" ^ label)
             ; Vdom.Attr.on_click (fun _ -> set_draft { draft with confidence = value }) ]
      [ text label ]
  in
  Vdom.Node.div
    ~attrs:[ Vdom.Attr.class_ "evidence" ]
    [ Vdom.Node.h3 [ text "Draft facade review" ]
    ; Vdom.Node.p [ text "This local draft demonstrates Bonsai state; it does not modify repository review artifacts." ]
    ; Vdom.Node.p (text "Evidence asset: " :: List.map evidence_ids ~f:evidence_button)
    ; Vdom.Node.label ~attrs:[ Vdom.Attr.for_ "draft-observation" ] [ text "Observation" ]
    ; Vdom.Node.textarea
        ~attrs:[ Vdom.Attr.id "draft-observation"
               ; Vdom.Attr.value_prop draft.observation
               ; Vdom.Attr.on_input (fun _event value -> set_draft { draft with observation = value }) ]
        []
    ; Vdom.Node.p
        [ text "Confidence: "
        ; confidence_button Draft_confidence.Low
        ; confidence_button Draft_confidence.Medium
        ; confidence_button Draft_confidence.High ]
    ; Vdom.Node.p [ text ("Draft confidence: " ^ Draft_confidence.label draft.confidence) ]
    ; Vdom.Node.p
        [ text
            (if Draft.Draft.is_complete draft
             then "Draft is complete and ready for a future export."
             else "Draft remains incomplete and cannot be exported.") ]
    ; export_link ]

let view_case case ~draft ~set_draft =
  let evidence =
    match case.Case.evidence with
    | [] -> Vdom.Node.p ~attrs:[ Vdom.Attr.class_ "muted" ] [ text "No permitted facade preview attached." ]
    | items ->
      Vdom.Node.div
        (List.map items ~f:(fun item ->
           Vdom.Node.div
             [ Vdom.Node.img
                 ~attrs:[ Vdom.Attr.src (preview_path item.Evidence.preview)
                        ; Vdom.Attr.alt (item.Evidence.epoch ^ " source preview") ] ()
             ; Vdom.Node.p
                 [ text (item.Evidence.epoch ^ " · " ^ item.Evidence.licence ^ " · "
                         ^ item.Evidence.credit ^ " · ")
                 ; link ~url:item.source_url "open source" ]
             ; Vdom.Node.p [ text item.Evidence.description ] ]))
  in
  Vdom.Node.div
    ~attrs:[ Vdom.Attr.class_ "case" ]
    [ Vdom.Node.h2 [ text case.name ]
    ; Vdom.Node.p ~attrs:[ Vdom.Attr.class_ "muted" ] [ text case.address ]
    ; Vdom.Node.div
        ~attrs:[ Vdom.Attr.class_ "claims" ]
        [ claim_card ~label:"Register age" ~value:case.register_value
            ~status:case.register_status ~note:case.register_note
        ; claim_card ~label:"Facade evidence" ~value:case.facade ~status:case.facade_status
            ~note:"Source-described style; visual annotation is pending."
        ; claim_card ~label:"Structural evidence" ~value:case.structure ~status:case.structure_status
            ~note:"Reconstruction proxy; image comparison is pending." ]
    ; Vdom.Node.div
        ~attrs:[ Vdom.Attr.class_ "evidence" ]
        [ Vdom.Node.h3 [ text "Attached evidence" ]; evidence ]
    ; Vdom.Node.div
        ~attrs:[ Vdom.Attr.class_ "evidence" ]
        [ Vdom.Node.h3 [ text "Structural image epochs" ]
        ; Vdom.Node.p [ text "Aligned crops are review aids, not structural findings." ]
        ; Vdom.Node.div
            (List.map case.Case.structural ~f:(fun item ->
               Vdom.Node.div
                 [ Vdom.Node.img
                     ~attrs:[ Vdom.Attr.src (preview_path item.Structural.preview)
                            ; Vdom.Attr.alt (item.Structural.epoch ^ " structural crop") ] ()
                 ; Vdom.Node.p [ text item.Structural.epoch ] ])) ]
    ; Vdom.Node.div
        ~attrs:[ Vdom.Attr.class_ "evidence" ]
        [ Vdom.Node.h3 [ text "Reviewer decisions" ]; review_view case.id ]
    ; draft_review ~draft
        ~evidence_ids:(List.map case.Case.evidence ~f:(fun item -> item.Evidence.asset_id))
        ~set_draft ]

let first_evidence_id case =
  List.hd case.Case.evidence
  |> Option.map ~f:(fun evidence -> evidence.Evidence.asset_id)
  |> Option.value ~default:""

let component () =
  let cases = Data.cases () in
  let initial_case =
    List.find cases ~f:(fun case -> String.equal case.Case.id "005")
    |> Option.value ~default:(List.hd_exn cases)
  in
  let%sub selected, set_selected =
    Bonsai.state (module String) ~default_model:initial_case.id
  in
  let%sub draft, set_draft =
    Bonsai.state
      (module Draft.Draft)
      ~default_model:(Draft.Draft.empty
                        ~source_id:initial_case.id
                        ~asset_id:(first_evidence_id initial_case))
  in
  let%arr selected = selected
  and set_selected = set_selected
  and draft = draft
  and set_draft = set_draft in
  let selected_case =
    List.find cases ~f:(fun case -> String.equal case.Case.id selected)
    |> Option.value ~default:(List.hd_exn cases)
  in
  let case_buttons =
    List.map cases ~f:(fun case ->
      Vdom.Node.button
        ~attrs:[ Vdom.Attr.on_click (fun _ ->
                   if String.equal case.Case.id selected
                   then Effect.Ignore
                   else
                     Effect.Many
                       [ set_selected case.Case.id
                       ; set_draft (Draft.Draft.empty
                                      ~source_id:case.Case.id
                                      ~asset_id:(first_evidence_id case))
                       ])
               ; Vdom.Attr.id ("case-" ^ case.Case.id)
               ; Vdom.Attr.class_ (if String.equal case.Case.id selected then "selected" else "")
               ; Vdom.Attr.create "aria-pressed" (Bool.to_string (String.equal case.Case.id selected)) ]
        [ text (case.Case.name ^ " · " ^ case.Case.address) ])
  in
  Vdom.Node.div
    ~attrs:[ Vdom.Attr.class_ "app" ]
    [ Vdom.Node.h1 [ text "Three Ages — Bonsai slice" ]
    ; Vdom.Node.p ~attrs:[ Vdom.Attr.class_ "muted" ]
        [ text (Int.to_string (List.length (Reviews.all ())) ^ " completed review records") ]
    ; Vdom.Node.p
        ~attrs:[ Vdom.Attr.class_ "lede" ]
        [ text "Typed evidence states with Python-generated data retained at the boundary." ]
    ; Vdom.Node.div ~attrs:[ Vdom.Attr.class_ "case-list" ] (Vdom.Node.h2 [ text "Pilot cases" ] :: case_buttons)
    ; view_case selected_case
        ~draft:(Draft.Draft.for_source draft
                  ~source_id:selected_case.id
                  ~asset_id:(first_evidence_id selected_case))
        ~set_draft ]

