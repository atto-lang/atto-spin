use std::io::Write;
use std::path::Path;

fn replace_once(source: &mut String, old: &str, new: &str) {
    assert_eq!(
        source.matches(old).count(),
        1,
        "fixture template drift: {old}"
    );
    *source = source.replacen(old, new, 1);
}
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<String> = std::env::args().collect();
    assert_eq!(
        args.len(),
        4,
        "usage: single-route shared|isolated INPUT.ores OUTPUT.ores"
    );
    assert!(matches!(args[1].as_str(), "shared" | "isolated"));
    let input = std::fs::canonicalize(&args[2])?;
    let mut source = std::fs::read_to_string(&input)?;
    replace_once(
        &mut source,
        "  val shared = http_routing.path(\"/shared\", arr[http_routing.literal(\"shared\")]);\n",
        "  val shared = http_routing.path(\"/probe\", arr[http_routing.literal(\"probe\")]);\n",
    );
    replace_once(&mut source,
        "  val isolated = http_routing.path(\"/isolated\", arr[http_routing.literal(\"isolated\")]);\n", "");
    replace_once(
        &mut source,
        "  val isolated_handler = http.handler(\"IsolatedLoad\").pooled(32);\n",
        "",
    );
    replace_once(&mut source, "  val isolated_registration = builder.get(rt borrow isolated, isolated_handler);\n  isolated_registration.unwrap();\n", "");
    if args[1] == "isolated" {
        replace_once(
            &mut source,
            "  val shared_handler = http.handler(\"SharedLoad\").pooled(32);\n",
            "  val shared_handler = http.handler(\"IsolatedLoad\").pooled(32);\n",
        );
    }
    let mut resolved = String::new();
    for line in source.lines() {
        if line.starts_with("import module ") {
            let (prefix, tail) = line.split_once(" from \"").ok_or("invalid import")?;
            let relative = tail
                .strip_suffix("\";")
                .ok_or("invalid import terminator")?;
            let path = std::fs::canonicalize(
                input
                    .parent()
                    .unwrap()
                    .join(relative)
                    .with_extension("ores"),
            )?;
            let escaped = path
                .to_str()
                .ok_or("non-UTF8 import path")?
                .replace('\\', "\\\\")
                .replace('"', "\\\"");
            resolved.push_str(&format!("{prefix} from \"{escaped}\";\n"));
        } else {
            resolved.push_str(line);
            resolved.push('\n');
        }
    }
    let output = Path::new(&args[3]);
    if let Some(parent) = output.parent() {
        std::fs::create_dir_all(parent)?;
    }
    // Never overwrite a prior experiment's generated source.
    std::fs::OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(output)?
        .write_all(resolved.as_bytes())?;
    Ok(())
}
