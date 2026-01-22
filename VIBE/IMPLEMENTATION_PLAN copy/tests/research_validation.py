#!/usr/bin/env python3
"""
Research-Focused Validation Tests

Tests CMBAgent with actual research-like tasks across all modes:
- One-shot: Quick calculations and plots
- Planning: Multi-step scientific workflows
- Control: Branching scientific hypotheses

Uses short, realistic prompts to verify end-to-end functionality.
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cmbagent import one_shot


class ResearchValidation:
    """Validate CMBAgent with research workflows"""

    def __init__(self):
        self.work_dir = Path.home() / ".cmbagent" / "validation" / f"run_{int(time.time())}"
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.results = []

    def log(self, message: str):
        """Log a message with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")

    def test(self, name: str, task: str, agent: str = 'engineer', model: str = 'gpt-4o-mini', max_round: int = 10):
        """Run a test with timing"""
        self.log(f"\n{'='*80}")
        self.log(f"TEST: {name}")
        self.log(f"Task: {task}")
        self.log(f"Agent: {agent} | Model: {model}")
        self.log(f"{'='*80}\n")

        test_work_dir = self.work_dir / name.lower().replace(" ", "_")
        test_work_dir.mkdir(exist_ok=True)

        start = time.time()
        success = False
        error = None

        try:
            result = one_shot(
                task=task,
                agent=agent,
                model=model,
                work_dir=str(test_work_dir),
                max_round=max_round
            )

            duration = time.time() - start
            success = result is not None

            if success:
                self.log(f"✓ PASSED in {duration:.2f}s")
                self.check_outputs(test_work_dir)
            else:
                self.log(f"✗ FAILED - No result returned")

        except Exception as e:
            duration = time.time() - start
            error = str(e)
            self.log(f"✗ FAILED in {duration:.2f}s")
            self.log(f"Error: {error}")

        self.results.append({
            'name': name,
            'task': task,
            'success': success,
            'duration': duration if 'duration' in locals() else 0,
            'error': error
        })

        return success

    def check_outputs(self, work_dir: Path):
        """Check what outputs were created"""
        outputs = []

        # Check for plots
        data_dir = work_dir / "data"
        if data_dir.exists():
            plots = list(data_dir.glob("*.png")) + list(data_dir.glob("*.jpg"))
            if plots:
                outputs.append(f"  📊 {len(plots)} plot(s): {', '.join(p.name for p in plots[:3])}")

        # Check for code
        codebase_dir = work_dir / "codebase"
        if codebase_dir.exists():
            code_files = list(codebase_dir.glob("*.py")) + list(codebase_dir.glob("*.json"))
            if code_files:
                outputs.append(f"  📝 {len(code_files)} file(s): {', '.join(f.name for f in code_files[:3])}")

        # Check for data files
        if data_dir and data_dir.exists():
            data_files = list(data_dir.glob("*.csv")) + list(data_dir.glob("*.txt")) + list(data_dir.glob("*.dat"))
            if data_files:
                outputs.append(f"  📁 {len(data_files)} data file(s): {', '.join(f.name for f in data_files[:3])}")

        if outputs:
            self.log("\nOutputs created:")
            for output in outputs:
                self.log(output)

    def run_validation_suite(self):
        """Run comprehensive validation across all modes"""

        self.log("\n" + "="*80)
        self.log("CMBAGENT RESEARCH VALIDATION SUITE")
        self.log("Testing all modes with realistic scientific tasks")
        self.log("="*80 + "\n")

        # =============================================================================
        # ONE-SHOT MODE: Simple, quick tasks
        # =============================================================================

        self.log("\n" + "="*80)
        self.log("MODE 1: ONE-SHOT (Quick Autonomous Execution)")
        self.log("="*80)

        self.test(
            name="OneShot_SimpleCalculation",
            task="Calculate the Hubble constant if H0 = 67.4 km/s/Mpc. Convert it to SI units (1/s).",
            max_round=5
        )

        self.test(
            name="OneShot_GeneratePlot",
            task="Generate a plot showing a simple CMB temperature power spectrum. Use ell values from 2 to 2500 and a rough Cl shape with peaks.",
            max_round=10
        )

        self.test(
            name="OneShot_DataAnalysis",
            task="Create random mock cosmological data (redshift, distance modulus) and calculate basic statistics (mean, std, median).",
            max_round=10
        )

        # =============================================================================
        # PLANNING MODE: Multi-step workflows (implicit planning by engineer agent)
        # =============================================================================

        self.log("\n" + "="*80)
        self.log("MODE 2: COMPLEX WORKFLOWS (Multi-Step Tasks)")
        self.log("="*80)

        self.test(
            name="Complex_DataPipeline",
            task="Create a data pipeline: 1) Generate random galaxy data (redshift, magnitude) 2) Calculate distances 3) Plot histogram 4) Save results to CSV",
            max_round=15
        )

        self.test(
            name="Complex_MultiPlot",
            task="Create a figure with 2 subplots: left shows sine wave, right shows cosine wave. Add labels and legend.",
            max_round=10
        )

        # =============================================================================
        # SCIENTIFIC CALCULATIONS
        # =============================================================================

        self.log("\n" + "="*80)
        self.log("MODE 3: SCIENTIFIC CALCULATIONS")
        self.log("="*80)

        self.test(
            name="Science_CosmologicalParameters",
            task="Calculate the age of the universe using Hubble constant H0=70 km/s/Mpc. Show calculation steps.",
            max_round=8
        )

        self.test(
            name="Science_AngularScale",
            task="Calculate the angular scale in degrees for a 1 Mpc object at redshift z=0.5, assuming a flat universe with H0=70 km/s/Mpc.",
            max_round=10
        )

        # =============================================================================
        # FILE AND DATA OPERATIONS
        # =============================================================================

        self.log("\n" + "="*80)
        self.log("MODE 4: FILE AND DATA OPERATIONS")
        self.log("="*80)

        self.test(
            name="FileOps_CreateJSON",
            task="Create a JSON file with cosmological parameters: H0, Omega_m, Omega_Lambda, sigma8. Use realistic values.",
            max_round=5
        )

        self.test(
            name="FileOps_ProcessData",
            task="Create mock observational data (100 points), calculate running average with window=5, and save both original and smoothed data.",
            max_round=12
        )

        # =============================================================================
        # ERROR HANDLING (Test retry mechanism)
        # =============================================================================

        self.log("\n" + "="*80)
        self.log("MODE 5: ERROR HANDLING AND RECOVERY")
        self.log("="*80)

        self.test(
            name="ErrorHandling_MissingModule",
            task="Try to use matplotlib to create a plot. If not imported, handle the error and import it correctly.",
            max_round=8
        )

        # =============================================================================
        # SUMMARY
        # =============================================================================

        self.print_summary()

    def print_summary(self):
        """Print validation summary"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r['success'])
        failed = total - passed

        self.log("\n" + "="*80)
        self.log("VALIDATION SUMMARY")
        self.log("="*80 + "\n")

        self.log(f"Total Tests:  {total}")
        self.log(f"Passed:       {passed} ✓")
        self.log(f"Failed:       {failed} ✗")
        self.log(f"Pass Rate:    {(passed/total*100):.1f}%\n")

        if failed > 0:
            self.log("Failed Tests:")
            for result in self.results:
                if not result['success']:
                    self.log(f"  ✗ {result['name']}")
                    if result['error']:
                        self.log(f"    Error: {result['error']}")

        self.log(f"\nWork directory: {self.work_dir}")
        self.log(f"Review outputs in subdirectories for each test\n")

        if failed == 0:
            self.log("="*80)
            self.log("✓ ALL TESTS PASSED - CMBAgent is working correctly!")
            self.log("="*80 + "\n")
        else:
            self.log("="*80)
            self.log(f"✗ {failed} test(s) failed - review errors above")
            self.log("="*80 + "\n")


def main():
    """Main entry point"""
    # Check environment
    if not os.getenv('OPENAI_API_KEY'):
        print("ERROR: OPENAI_API_KEY not set")
        print("Please set your API key in .env file or environment")
        return 1

    validator = ResearchValidation()

    try:
        validator.run_validation_suite()
        return 0
    except KeyboardInterrupt:
        print("\n\nValidation interrupted by user")
        return 130
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
