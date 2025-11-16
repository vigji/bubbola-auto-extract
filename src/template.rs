use once_cell::sync::Lazy;
use serde_json::Value;

const RAW_TEMPLATE: &str = include_str!("../schema/page_extraction_template.json");

static TEMPLATE_VALUE: Lazy<Value> = Lazy::new(|| {
    serde_json::from_str(RAW_TEMPLATE).expect("page extraction template must contain valid JSON")
});

/// Returns the canonical extraction template as a parsed `serde_json::Value`.
pub fn extraction_template() -> &'static Value {
    &TEMPLATE_VALUE
}

/// Returns the canonical extraction template as a raw JSON string.
pub fn extraction_template_json() -> &'static str {
    RAW_TEMPLATE
}
