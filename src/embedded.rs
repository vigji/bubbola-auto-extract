pub(crate) mod data {
    include!(concat!(env!("OUT_DIR"), "/ground_truth.rs"));
}

pub(crate) fn ground_truth_bytes() -> &'static [u8] {
    data::GROUND_TRUTH_BYTES
}

pub fn build_info_json() -> &'static str {
    data::BUILD_INFO_JSON
}
