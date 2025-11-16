use std::path::PathBuf;

use anyhow::{Context, Result};
use clap::Parser;
use pdf_eval::embedded;
use pdf_eval::evaluator::{
    evaluate_predictions, load_ground_truth_from_embed, load_ground_truth_from_path,
    load_predictions,
};
use pdf_eval::metrics::EvaluationMetrics;
use pdf_eval::template;

#[derive(Debug, Parser)]
#[command(about = "Score prediction JSON files against an embedded ground truth.")]
struct Args {
    #[arg(long, help = "Path to the predictions JSON file")]
    predictions: Option<PathBuf>,

    #[arg(long, help = "Optional path to an alternate ground truth JSON file")]
    ground_truth: Option<PathBuf>,

    #[arg(long, help = "Write metrics to this path instead of stdout")]
    output: Option<PathBuf>,

    #[arg(long, help = "Print build metadata and exit")]
    info: bool,

    #[arg(long, help = "Print the extraction template JSON and exit")]
    template: bool,
}

fn main() -> Result<()> {
    let args = Args::parse();

    if args.info {
        println!("{}", embedded::build_info_json());
        return Ok(());
    }

    if args.template {
        println!("{}", template::extraction_template_json());
        return Ok(());
    }

    let predictions_path = args
        .predictions
        .as_deref()
        .context("--predictions is required unless --info is specified")?;

    let ground_truth = if let Some(path) = &args.ground_truth {
        load_ground_truth_from_path(path)
            .with_context(|| format!("failed to load ground truth from {}", path.display()))?
    } else {
        load_ground_truth_from_embed().context("embedded ground truth is missing")?
    };

    let predictions = load_predictions(predictions_path).with_context(|| {
        format!(
            "failed to load predictions from {}",
            predictions_path.display()
        )
    })?;

    let metrics = evaluate_predictions(&ground_truth, &predictions)
        .context("failed to compute evaluation metrics")?;

    emit_metrics(&metrics, args.output.as_deref())?;
    Ok(())
}

fn emit_metrics(metrics: &EvaluationMetrics, output: Option<&std::path::Path>) -> Result<()> {
    let payload = serde_json::to_string_pretty(metrics)?;
    if let Some(path) = output {
        std::fs::write(path, payload.clone() + "\n")
            .with_context(|| format!("failed to write {}", path.display()))?;
    }
    println!("{}", payload);
    Ok(())
}
