"""
Enhance input text endpoints.
"""

import os
import json
import tempfile

from fastapi import APIRouter, HTTPException

from models.schemas import EnhanceInputRequest, EnhanceInputResponse

router = APIRouter(prefix="/api", tags=["Enhance"])

# Import cmbagent at runtime
_cmbagent = None


def _get_cmbagent():
    """Lazy load cmbagent module."""
    global _cmbagent
    if _cmbagent is None:
        try:
            import cmbagent
            _cmbagent = cmbagent
        except ImportError as e:
            raise HTTPException(
                status_code=500,
                detail=f"CMBAgent module not available: {str(e)}"
            )
    return _cmbagent


@router.post("/enhance-input", response_model=EnhanceInputResponse)
async def enhance_input_endpoint(request: EnhanceInputRequest):
    """
    Enhance input text with contextual information from referenced arXiv papers.

    Args:
        request: EnhanceInputRequest containing input_text and processing options

    Returns:
        EnhanceInputResponse with enhanced text and cost breakdown
    """
    try:
        print(f"Processing enhance-input request...")
        print(f"Input text length: {len(request.input_text)} characters")
        print(f"Max workers: {request.max_workers}")
        print(f"Max depth: {request.max_depth}")
        if request.work_dir:
            print(f"Work directory: {request.work_dir}")

        cmbagent = _get_cmbagent()

        # Use work_dir from request or create a temporary one
        work_dir = request.work_dir
        if not work_dir:
            # Create a temporary directory for processing
            work_dir = tempfile.mkdtemp(prefix="enhance_input_")
            print(f"Created temporary work directory: {work_dir}")

        # Check if enhanced_input.md already exists to avoid re-processing
        enhanced_input_file = os.path.join(work_dir, "enhanced_input.md")
        if request.work_dir and os.path.exists(enhanced_input_file):
            # Read existing enhanced text if work_dir was provided and file exists
            with open(enhanced_input_file, 'r', encoding='utf-8') as f:
                enhanced_text = f.read()
            print("Using existing enhanced_input.md file")
        else:
            # Call the preprocess_task function
            enhanced_text = cmbagent.preprocess_task(
                text=request.input_text,
                work_dir=work_dir,
                max_workers=request.max_workers,
                max_depth=request.max_depth,
                clear_work_dir=False  # Don't clear when work_dir is provided
            )

        # Collect cost information
        cost_breakdown = {}
        processing_summary = {}

        # Try to read OCR costs if available
        ocr_cost_file = os.path.join(work_dir, "ocr_cost.json")
        if os.path.exists(ocr_cost_file):
            try:
                with open(ocr_cost_file, 'r') as f:
                    ocr_data = json.load(f)
                    cost_breakdown['ocr'] = {
                        'total_cost': ocr_data.get('total_cost_usd', 0),
                        'pages_processed': ocr_data.get('total_pages_processed', 0),
                        'files_processed': len(ocr_data.get('entries', []))
                    }
            except Exception as e:
                print(f"Warning: Could not read OCR cost file: {e}")

        # Try to read summary processing costs
        summaries_dir = os.path.join(work_dir, "summaries")
        if os.path.exists(summaries_dir):
            summary_cost_files = []
            for root, dirs, files in os.walk(summaries_dir):
                for file in files:
                    if file.startswith('cost_report_') and file.endswith('.json'):
                        summary_cost_files.append(os.path.join(root, file))

            total_summary_cost = 0
            all_agent_costs = []

            for cost_file in summary_cost_files:
                try:
                    with open(cost_file, 'r') as f:
                        cost_data = json.load(f)
                        # Each cost file contains an array of agent cost entries
                        if isinstance(cost_data, list):
                            for entry in cost_data:
                                if isinstance(entry, dict) and entry.get('Agent') != 'Total':
                                    cost_usd = entry.get('Cost ($)', 0)
                                    # Check for valid number (not NaN/inf)
                                    if isinstance(cost_usd, (int, float)) and not (
                                        isinstance(cost_usd, float) and
                                        (cost_usd != cost_usd or cost_usd == float('inf'))
                                    ):
                                        total_summary_cost += cost_usd
                                        all_agent_costs.append({
                                            'agent': entry.get('Agent', 'Unknown'),
                                            'cost': cost_usd,
                                            'model': entry.get('Model', 'N/A'),
                                            'prompt_tokens': entry.get('Prompt Tokens', 0),
                                            'completion_tokens': entry.get('Completion Tokens', 0),
                                            'total_tokens': entry.get('Total Tokens', 0)
                                        })
                except Exception as e:
                    print(f"Warning: Could not read summary cost file {cost_file}: {e}")

            if all_agent_costs:
                cost_breakdown['summarization'] = {
                    'total_cost': total_summary_cost,
                    'agents': all_agent_costs
                }

        # Calculate total cost
        total_cost = 0
        if 'ocr' in cost_breakdown:
            total_cost += cost_breakdown['ocr']['total_cost']
        if 'summarization' in cost_breakdown:
            total_cost += cost_breakdown['summarization']['total_cost']

        cost_breakdown['total'] = total_cost

        # Create processing summary
        processing_summary = {
            'enhanced_text_length': len(enhanced_text),
            'original_text_length': len(request.input_text),
            'enhancement_added': len(enhanced_text) > len(request.input_text),
            'work_dir': work_dir
        }

        # Create success response
        return EnhanceInputResponse(
            status="success",
            enhanced_text=enhanced_text,
            processing_summary=processing_summary,
            cost_breakdown=cost_breakdown,
            message=f"Successfully enhanced input text. Total cost: ${total_cost:.4f}"
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error in enhance_input_endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing enhance-input request: {str(e)}"
        )
