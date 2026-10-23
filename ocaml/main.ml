open Bonsai_web

let () = Start.start ~bind_to_element_with_id:"app" (App.component ())
