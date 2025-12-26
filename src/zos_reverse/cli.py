"""Command-line interface for z/OS reverse engineering tool"""

import click
import logging
import sys
from pathlib import Path
from typing import Optional, List
import structlog
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table

from .pipeline import ReverseEngineeringPipeline
from .reporter import ReportWriter

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()
console = Console()


@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.option('--debug', is_flag=True, help='Enable debug output')
def main(verbose: bool, debug: bool):
    """z/OS Binary Reverse Engineering Tool"""
    if debug:
        logging.basicConfig(level=logging.DEBUG)
    elif verbose:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)


@main.command()
@click.argument('input_file', type=click.Path(exists=True, path_type=Path))
@click.option('--output-dir', '-o', type=click.Path(path_type=Path), 
              default='./output', help='Output directory for results')
@click.option('--format', '-f', multiple=True, 
              type=click.Choice(['text', 'yaml', 'json', 'asm', 'pseudocode']),
              default=['text', 'yaml', 'asm', 'pseudocode'],
              help='Output formats to generate')
@click.option('--decoder', type=click.Choice(['native', 'external']),
              default='native', help='Decoder to use')
@click.option('--include-cfg', is_flag=True, help='Include CFG visualization')
@click.option('--include-callgraph', is_flag=True, help='Include call graph')
def analyze(input_file: Path, output_dir: Path, format: tuple, 
            decoder: str, include_cfg: bool, include_callgraph: bool):
    """Analyze a single z/OS binary file"""
    
    console.print(f"[bold blue]Analyzing:[/bold blue] {input_file}")
    console.print(f"[bold blue]Output to:[/bold blue] {output_dir}")
    
    try:
        # Create pipeline
        pipeline = ReverseEngineeringPipeline(decoder_type=decoder)
        
        # Process file
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Processing...", total=5)
            
            progress.update(task, description="Loading binary...", advance=1)
            result = pipeline.process_file(input_file, progress_callback=lambda msg: 
                                          progress.update(task, description=msg, advance=1))
            
            progress.update(task, description="Generating reports...", advance=1)
            
        if result:
            # Generate reports
            writer = ReportWriter(output_dir)
            output_files = writer.write_reports(result, base_name=input_file.stem, 
                                               formats=list(format))
            
            # Display results summary
            _display_results_summary(result, output_files)
            
            console.print("\n[bold green]✓ Analysis complete![/bold green]")
        else:
            console.print("[bold red]✗ Analysis failed![/bold red]", style="bold red")
            sys.exit(1)
            
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        logger.exception("Analysis failed")
        sys.exit(1)


@main.command()
@click.argument('input_dir', type=click.Path(exists=True, path_type=Path, file_okay=False))
@click.option('--output-dir', '-o', type=click.Path(path_type=Path),
              default='./output', help='Output directory for results')
@click.option('--pattern', '-p', default='*', help='File pattern to match (glob)')
@click.option('--format', '-f', multiple=True,
              type=click.Choice(['text', 'yaml', 'json', 'asm', 'pseudocode']),
              default=['yaml', 'asm'],
              help='Output formats to generate')
@click.option('--decoder', type=click.Choice(['native', 'external']),
              default='native', help='Decoder to use')
@click.option('--max-files', type=int, help='Maximum number of files to process')
def batch(input_dir: Path, output_dir: Path, pattern: str, format: tuple,
          decoder: str, max_files: Optional[int]):
    """Process multiple z/OS binary files in batch"""
    
    console.print(f"[bold blue]Batch processing:[/bold blue] {input_dir}")
    console.print(f"[bold blue]Pattern:[/bold blue] {pattern}")
    console.print(f"[bold blue]Output to:[/bold blue] {output_dir}")
    
    # Find files
    files = list(input_dir.glob(pattern))
    if max_files:
        files = files[:max_files]
    
    if not files:
        console.print(f"[yellow]No files found matching pattern: {pattern}[/yellow]")
        return
    
    console.print(f"[bold]Found {len(files)} files to process[/bold]")
    
    # Create pipeline
    pipeline = ReverseEngineeringPipeline(decoder_type=decoder)
    writer = ReportWriter(output_dir)
    
    results = {}
    failed = []
    
    # Process each file
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        "[progress.percentage]{task.percentage:>3.0f}%",
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Processing files...", total=len(files))
        
        for file_path in files:
            progress.update(task, description=f"Processing {file_path.name}...")
            
            try:
                result = pipeline.process_file(file_path)
                if result:
                    results[file_path.stem] = result
                    
                    # Generate reports for this file
                    subdir = output_dir / file_path.stem
                    subdir.mkdir(parents=True, exist_ok=True)
                    writer_individual = ReportWriter(subdir)
                    writer_individual.write_reports(result, base_name=file_path.stem,
                                                   formats=list(format))
                else:
                    failed.append(file_path)
                    
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")
                failed.append(file_path)
            
            progress.update(task, advance=1)
    
    # Write portfolio index
    if results:
        index_file = writer.write_portfolio_index(results)
        console.print(f"\n[bold]Portfolio index:[/bold] {index_file}")
    
    # Display summary
    _display_batch_summary(results, failed)
    
    if failed:
        console.print(f"\n[yellow]⚠ {len(failed)} files failed processing[/yellow]")
        for f in failed[:10]:  # Show first 10
            console.print(f"  - {f}")
        if len(failed) > 10:
            console.print(f"  ... and {len(failed) - 10} more")
    
    console.print(f"\n[bold green]✓ Batch processing complete![/bold green]")


@main.command()
def info():
    """Display tool information and capabilities"""
    console.print("\n[bold]z/OS Binary Reverse Engineering Tool - MVP[/bold]\n")
    
    table = Table(title="Capabilities")
    table.add_column("Feature", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Description")
    
    capabilities = [
        ("Binary Ingestion", "✓", "Load module and program object support"),
        ("Disassembly", "✓", "z/Architecture instruction decoding"),
        ("CFG Building", "✓", "Control flow graph construction"),
        ("Procedure Detection", "✓", "Heuristic-based procedure inference"),
        ("Assembler Reconstruction", "✓", "HLASM-like output with synthetic labels"),
        ("Pseudocode Generation", "✓", "Structured control flow representation"),
        ("Multi-format Output", "✓", "Text, YAML, JSON, ASM, Pseudocode"),
        ("Batch Processing", "✓", "Portfolio analysis support"),
        ("External Decoder", "Partial", "Interface available, implementation pending"),
        ("LE Detection", "Future", "Language Environment conformance"),
        ("Data Flow Analysis", "Future", "Register liveness and data tracking"),
        ("Java Transformation", "Future", "Not in MVP scope"),
    ]
    
    for feature, status, desc in capabilities:
        status_icon = {"✓": "[green]✓[/green]", 
                      "Partial": "[yellow]◐[/yellow]",
                      "Future": "[dim]○[/dim]"}.get(status, status)
        table.add_row(feature, status_icon, desc)
    
    console.print(table)
    
    console.print("\n[bold]Supported z/Architecture Instructions:[/bold]")
    console.print("• RR, RX, RS, SI, SS formats")
    console.print("• Extended formats: RRE, RXE, RXY, RSY, RIL")
    console.print("• Branch/Call detection: BC, BCR, BAL, BALR, BASR")
    console.print("• Common operations: Load, Store, Arithmetic, Logic, Compare")
    
    console.print("\n[bold]Detection Methods:[/bold]")
    console.print("• Entry point analysis")
    console.print("• Call target identification")  
    console.print("• Prologue pattern matching (STM 14,12,...)")
    console.print("• Control flow structure analysis")
    
    console.print("\n[bold]Evidence & Traceability:[/bold]")
    console.print("• Every output maps to instruction addresses")
    console.print("• Confidence scores for inferred constructs")
    console.print("• Explicit UNKNOWN regions marked")
    console.print("• Deterministic, repeatable analysis")


def _display_results_summary(result, output_files):
    """Display analysis results summary"""
    
    # Create summary table
    table = Table(title="Analysis Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    
    stats = result.statistics
    table.add_row("Instructions Decoded", str(stats.get('instruction_count', 0)))
    table.add_row("Decode Rate", f"{stats.get('decode_rate', 0):.1%}")
    table.add_row("Basic Blocks", str(len(result.cfg.basic_blocks)))
    table.add_row("Procedures", str(len(result.cfg.procedures)))
    table.add_row("Branches", str(stats.get('branch_count', 0)))
    table.add_row("Calls", str(stats.get('call_count', 0)))
    table.add_row("Returns", str(stats.get('return_count', 0)))
    table.add_row("Unknown Regions", str(len(result.unknown_regions)))
    
    console.print(table)
    
    # Show output files
    console.print("\n[bold]Output Files:[/bold]")
    for fmt, path in output_files.items():
        console.print(f"  • {fmt}: {path}")


def _display_batch_summary(results, failed):
    """Display batch processing summary"""
    
    table = Table(title="Batch Processing Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    
    total_instructions = sum(r.statistics.get('instruction_count', 0) for r in results.values())
    total_procedures = sum(len(r.cfg.procedures) for r in results.values())
    avg_decode_rate = (sum(r.statistics.get('decode_rate', 0) for r in results.values()) / 
                      len(results)) if results else 0
    
    table.add_row("Modules Processed", str(len(results)))
    table.add_row("Failed", str(len(failed)))
    table.add_row("Total Instructions", str(total_instructions))
    table.add_row("Total Procedures", str(total_procedures))
    table.add_row("Average Decode Rate", f"{avg_decode_rate:.1%}")
    
    console.print(table)


if __name__ == '__main__':
    main()
