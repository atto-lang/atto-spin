#[path = "../stats.rs"]
mod stats;
use serde_json::{json, Value};
use std::collections::{BTreeMap, BTreeSet};
use std::io::{BufRead, BufReader};
use std::path::Path;

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();
    assert_eq!(args.len(), 2, "usage: summarize RUN_DIRECTORY");
    let root = Path::new(&args[1]);
    let result: Value = serde_json::from_reader(std::fs::File::open(root.join("result.json"))?)?;
    let mut groups: BTreeMap<String, Vec<u64>> = BTreeMap::new();
    let mut traces: BTreeMap<String, BTreeMap<String, usize>> = BTreeMap::new();
    let mut core_end = Value::Null;
    let mut core_begin = Value::Null;
    for file in ["stdout.log", "stderr.log"] {
        for line in BufReader::new(std::fs::File::open(root.join(file))?).lines() {
            let line = line?;
            if !line.starts_with('{') {
                continue;
            }
            let row: Value = serde_json::from_str(&line)?;
            match (
                row["schema"].as_str(),
                row["kind"].as_str(),
                row["signal"].as_str(),
            ) {
                (Some("ores-core-perf.v1"), Some("begin"), _) => core_begin = row,
                (Some("ores-core-perf.v1"), Some("end"), _) => core_end = row,
                (Some("ores-core-perf.v1"), Some("phase"), _) => {
                    // Conservative exclusion of the first 15 seconds from core
                    // configuration; independent from client warm-up clocks.
                    if row["start_ns"].as_u64().ok_or("missing core timestamp")? >= 15_000_000_000 {
                        let phase = row["phase"].as_str().ok_or("missing phase")?;
                        groups
                            .entry(format!("warm.core.{phase}"))
                            .or_default()
                            .push(row["duration_ns"].as_u64().ok_or("invalid core duration")?);
                    }
                }
                (Some("oreslang-otel.v1"), _, Some("metric")) => {
                    let name = row["name"]
                        .as_str()
                        .ok_or("missing metric name")?
                        .to_string();
                    let trace = row["ores_trace_id"]
                        .as_str()
                        .ok_or("missing trace")?
                        .to_string();
                    *traces
                        .entry(trace)
                        .or_default()
                        .entry(name.clone())
                        .or_default() += 1;
                    groups
                        .entry(format!("warm.otel.{name}"))
                        .or_default()
                        .push(row["value"].as_u64().ok_or("invalid metric value")?);
                }
                _ => {}
            }
        }
    }
    let expected: BTreeSet<String> = [
        "admission.to_claim",
        "mailbox.move_to_claim",
        "actor.prepare",
        "response.await",
        "admission.to_response_continuation",
        "admission.to_dispatch",
        "routing.dispatch",
    ]
    .iter()
    .map(|s| s.to_string())
    .collect();
    if result["sample_every"].as_u64().unwrap_or(0) != 0 {
        if traces.len() as u64
            != result["sampled_requests"]
                .as_u64()
                .ok_or("missing sample count")?
        {
            return Err("sampled request count differs from exported trace count".into());
        }
        for names in traces.values() {
            if names.keys().cloned().collect::<BTreeSet<_>>() != expected
                || names.values().any(|count| *count != 1)
            {
                return Err("missing or duplicate sampled request metrics".into());
            }
        }
    }
    let mut phases = BTreeMap::new();
    for (name, mut values) in groups {
        let count = values.len();
        let mean = values.iter().map(|v| *v as f64).sum::<f64>() / count as f64 / 1_000_000.0;
        let mut distribution = stats::distribution(&mut values);
        distribution["count"] = json!(count);
        distribution["mean_ms"] = json!(mean);
        phases.insert(name, distribution);
    }
    let summary = json!({"core_begin":core_begin, "core_end":core_end, "core_warm_exclusion_ns":15000000000u64, "complete_otel_traces":traces.len(), "phases":phases});
    std::fs::write(
        root.join("phases.json"),
        serde_json::to_string_pretty(&summary)?,
    )?;
    println!("{}", summary);
    Ok(())
}
