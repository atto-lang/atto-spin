mod http;
mod stats;
use serde_json::json;
use std::collections::BTreeSet;
use std::sync::{Arc, Barrier};
use std::time::{Duration, Instant};

#[derive(Default)]
struct ClientResult {
    response_ns: Vec<u64>,
    scheduled_ns: Vec<u64>,
    lag_ns: Vec<u64>,
    workers: BTreeSet<String>,
    reused: usize,
    error: Option<String>,
}
fn main() {
    let args: Vec<String> = std::env::args().collect();
    assert_eq!(
        args.len(),
        6,
        "usage: spin-paced-load PORT shared|isolated SECONDS SAMPLE_EVERY OUTPUT.json"
    );
    let port: u16 = args[1].parse().unwrap();
    let mode = args[2].clone();
    assert!(matches!(mode.as_str(), "shared" | "isolated"));
    let seconds: u64 = args[3].parse().unwrap();
    assert!((1..=600).contains(&seconds));
    let sample_every: u64 = args[4].parse().unwrap();
    let clients = 100;
    let barrier = Arc::new(Barrier::new(clients + 1));
    let start = Instant::now() + Duration::from_secs(2);
    let measured_start = start + Duration::from_secs(10);
    let end = measured_start + Duration::from_secs(seconds);
    let handles: Vec<_> = (0..clients)
        .map(|id| {
            let barrier = barrier.clone();
            let mode = mode.clone();
            std::thread::spawn(move || {
                let connection = http::Connection::connect(port);
                barrier.wait();
                let mut result = ClientResult::default();
                let mut connection = match connection {
                    Ok(c) => c,
                    Err(e) => {
                        result.error = Some(e.to_string());
                        return result;
                    }
                };
                // Each persistent connection has 100 scheduled slots/sec and at most
                // one outstanding request. Overdue slots are skipped, never caught
                // up in a burst. Missed slots remain in the target denominator.
                let interval = Duration::from_millis(10);
                let mut slot = start + Duration::from_micros(id as u64 * 100);
                let mut sequence = id as u64;
                while slot < end {
                    let now = Instant::now();
                    if now > slot + interval {
                        let skip = ((now - slot).as_nanos() / interval.as_nanos()) as u32;
                        slot += interval * skip;
                    }
                    if slot >= end {
                        break;
                    }
                    if let Some(wait) = slot.checked_duration_since(Instant::now()) {
                        std::thread::sleep(wait);
                    }
                    let sent = Instant::now();
                    if sent >= end {
                        break;
                    }
                    sequence += 100;
                    let response = connection.request(
                        port,
                        &mode,
                        sample_every != 0 && sequence.is_multiple_of(sample_every),
                    );
                    let completed = Instant::now();
                    match response {
                        Ok(response) => {
                            if slot >= measured_start {
                                result
                                    .response_ns
                                    .push((completed - sent).as_nanos() as u64);
                                result
                                    .scheduled_ns
                                    .push((completed - slot).as_nanos() as u64);
                                result
                                    .lag_ns
                                    .push(sent.saturating_duration_since(slot).as_nanos() as u64);
                                result.workers.insert(response.worker);
                                result.reused += usize::from(response.reused);
                            }
                        }
                        Err(error) => {
                            result.error = Some(error.to_string());
                            break;
                        }
                    }
                    slot += interval;
                }
                result
            })
        })
        .collect();
    barrier.wait();
    let mut aggregate = ClientResult::default();
    let mut errors = Vec::new();
    for handle in handles {
        let result = handle.join().expect("client panicked");
        aggregate.response_ns.extend(result.response_ns);
        aggregate.scheduled_ns.extend(result.scheduled_ns);
        aggregate.lag_ns.extend(result.lag_ns);
        aggregate.workers.extend(result.workers);
        aggregate.reused += result.reused;
        if let Some(error) = result.error {
            errors.push(error);
        }
    }
    let successes = aggregate.response_ns.len();
    let target_slots = seconds * 10000;
    let summary = json!({"schema":"spin-paced-load.v1", "mode":mode, "clients":clients, "target_rps":10000,
        "warmup_seconds":10, "measurement_seconds":seconds, "target_slots":target_slots,
        "successes":successes, "missed_or_failed_slots":target_slots.saturating_sub(successes as u64),
        "achieved_rps":successes as f64 / seconds as f64, "failed_clients":errors.len(), "errors":errors,
        "reconnects":0, "reused_responses":aggregate.reused, "worker_ids":aggregate.workers,
        "response_latency":stats::distribution(&mut aggregate.response_ns),
        "scheduled_latency":stats::distribution(&mut aggregate.scheduled_ns),
        "client_start_lag":stats::distribution(&mut aggregate.lag_ns),
        "sample_every":sample_every});
    std::fs::write(&args[5], serde_json::to_string_pretty(&summary).unwrap()).unwrap();
    println!("{}", summary);
    if !errors.is_empty() {
        std::process::exit(1);
    }
}
