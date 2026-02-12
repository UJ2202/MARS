"""
arXiv filter and download endpoints.
"""

from fastapi import APIRouter, HTTPException

from models.schemas import ArxivFilterRequest, ArxivFilterResponse

from core.logging import get_logger
logger = get_logger(__name__)

router = APIRouter(prefix="/api/arxiv", tags=["ArXiv"])

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


@router.post("/filter", response_model=ArxivFilterResponse)
async def arxiv_filter_endpoint(request: ArxivFilterRequest):
    """
    Extract arXiv URLs from input text and download corresponding PDFs.

    Args:
        request: ArxivFilterRequest containing input_text and optional work_dir

    Returns:
        ArxivFilterResponse with download results and metadata
    """
    try:
        logger.info("arxiv_filter_request_started")
        logger.debug("arxiv_input_length", length=len(request.input_text))
        if request.work_dir:
            logger.debug("arxiv_work_dir", work_dir=request.work_dir)

        cmbagent = _get_cmbagent()

        # Use work_dir from request or fall back to cmbagent's default
        work_dir = request.work_dir if request.work_dir else None

        # Call the arxiv_filter function
        result = cmbagent.arxiv_filter(
            input_text=request.input_text,
            work_dir=work_dir
        )

        # Create success response
        return ArxivFilterResponse(
            status="success",
            result=result,
            message=f"Successfully processed {result['downloads_successful']} downloads out of {len(result['urls_found'])} URLs found"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("arxiv_filter_failed", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Error processing arXiv filter request: {str(e)}"
        )
