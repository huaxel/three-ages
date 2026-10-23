module Draft_confidence = struct
  type t = Unassigned | Low | Medium | High [@@deriving sexp, equal]

  let label = function
    | Unassigned -> "unassigned"
    | Low -> "low"
    | Medium -> "medium"
    | High -> "high"
end

module Claim_status = struct
  type t = Pending | Proxy | Source_description | Documented_proxy | Reviewed
  [@@deriving sexp, equal]

  let label = function
    | Pending -> "pending"
    | Proxy -> "proxy"
    | Source_description -> "source description"
    | Documented_proxy -> "documented proxy"
    | Reviewed -> "reviewed"
end

module Evidence = struct
  type t = {
    asset_id : string;
    epoch : string;
    description : string;
    source_url : string;
    preview : string;
    licence : string;
    credit : string;
  }
end

module Structural = struct
  type t = {
    epoch : string;
    preview : string;
  }
end

module Case = struct
  type t = {
    id : string;
    name : string;
    address : string;
    register_value : string;
    register_status : Claim_status.t;
    register_note : string;
    facade : string;
    facade_status : Claim_status.t;
    structure : string;
    structure_status : Claim_status.t;
    evidence : Evidence.t list;
    structural : Structural.t list;
  }
end
