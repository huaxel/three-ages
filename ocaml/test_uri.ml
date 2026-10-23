let () =
  let url = Uri.of_string "HTTPS://example.com" in
  match Uri.scheme url with
  | Some s -> print_endline s
  | None -> print_endline "None"
