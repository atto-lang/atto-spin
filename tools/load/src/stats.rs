use serde_json::{json, Value};
pub fn distribution(samples: &mut [u64]) -> Value {
    samples.sort_unstable();
    if samples.is_empty() {
        return Value::Null;
    }
    let percentile = |p: usize| {
        samples[((samples.len() * p).div_ceil(100) - 1).min(samples.len() - 1)] as f64 / 1_000_000.0
    };
    json!({"p50_ms": percentile(50), "p95_ms": percentile(95), "p99_ms": percentile(99), "max_ms": samples[samples.len()-1] as f64 / 1_000_000.0})
}
#[cfg(test)]
mod tests {
    #[test]
    fn nearest_rank_handles_singleton_and_tail() {
        let mut values: Vec<u64> = (1..=100).rev().map(|x| x * 1_000_000).collect();
        assert_eq!(super::distribution(&mut values)["p99_ms"], 99.0);
        assert_eq!(super::distribution(&mut [7_000_000])["p50_ms"], 7.0);
        assert!(super::distribution(&mut []).is_null());
    }
}
