export interface ParcelSummary {
  id: number;
  state: string;
  county: string;
  parcel_id: string;
  owner_name: string | null;
  full_address: string | null;
  billed_amount: number | null;
  decision: string | null;
  risk_score: number | null;
  review_status: string | null;
  final_approved: boolean | null;
  property_type: string | null;
}

export interface ParcelDetail {
  id: number;
  state: string;
  county: string;
  parcel_id: string;
  address: string | null;
  full_address: string | null;
  owner_name: string | null;
  owner_mailing_address: string | null;
  billed_amount: number | null;
  legal_class: string | null;
  latitude: number | null;
  longitude: number | null;
  google_maps_url: string | null;
  street_view_url: string | null;
  zillow_url: string | null;
  realtor_url: string | null;
  assessor_url: string | null;
  treasurer_url: string | null;
  lot_size_acres: number | null;
  lot_size_sqft: number | null;
  zoning_code: string | null;
  assessed_total_value: number | null;
  legal_description: string | null;
  // Assessment fields
  assessment_id: number | null;
  decision: string | null;
  risk_score: number | null;
  kill_switch: string | null;
  max_bid: number | null;
  property_type: string | null;
  ownership_type: string | null;
  critical_warning: string | null;
  assessment_status: string | null;
  review_status: string | null;
  check_street_view: boolean;
  check_street_view_notes: string | null;
  check_power_lines: boolean;
  check_topography: boolean;
  check_topography_notes: string | null;
  check_water_test: boolean;
  check_water_notes: string | null;
  check_access_frontage: boolean;
  check_frontage_ft: number | null;
  check_rooftop_count: boolean;
  check_rooftop_pct: number | null;
  final_legal_matches_map: boolean;
  final_hidden_structure: boolean;
  final_who_cuts_grass: string | null;
  final_approved: boolean | null;
  reviewer_notes: string | null;
  reviewed_at: string | null;
}

export interface SearchResponse {
  total: number;
  parcels: ParcelSummary[];
  limit: number;
  offset: number;
}

export interface DashboardStats {
  state: string;
  county: string;
  total_parcels: number;
  assessed: number;
  bids: number;
  reviewed: number;
  approved: number;
  pending_review: number;
}
